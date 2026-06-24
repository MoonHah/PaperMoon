from pydantic_settings import BaseSettings, SettingsConfigDict

# JWT 密钥的开发占位默认值。生产必须用环境变量 JWT_SECRET 覆盖；
# 否则 main.py 的 lifespan 启动校验会在非 debug 下拒绝启动（防伪造 token）。
DEV_JWT_SECRET = "dev-insecure-change-me-please-override-in-production"


class Settings(BaseSettings):
    app_name: str = "PaperMoon"
    app_version: str = "0.1.0"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8008

    # PostgreSQL
    database_url: str = "postgresql://postgres:postgres@localhost:5432/papermoon"

    # Qdrant Vector Database
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "papermoon"
    vector_size: int = 1536
    qdrant_timeout: int = 5

    # LLM
    llm_mode: str = "mock"               # "mock" | "openai"
    llm_model: str = "gpt-4o-mini"
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"

    # Embedding
    embedding_mode: str = "mock"         # "mock" | "openai"
    embedding_model: str = "text-embedding-3-small"

    # Retrieval strategy
    retrieval_mode: str = "simple"       # "simple" | "multi_query" | "hyde"
    multi_query_count: int = 3
    retrieval_temperature: float = 0.0   # 含 LLM 的检索策略生成温度（0=可复现）
    # 相关性阈值门控：低于此余弦分数的 chunk 视为无关被丢弃（全丢→空→agent 据 grounding 如实
    # 回"无相关内容"，不再拿噪声硬凑）。0 = 关闭（不过滤）。须按 embedding 模型+语料经验调参：
    # text-embedding-3-small 经验区间——相关 ~0.3+、无关 <0.2。先看 vector.search 日志的分数分布再定。
    retrieval_score_threshold: float = 0.0

    # Agent（统一为 LangGraph 后端）
    checkpoint_backend: str = "memory"   # "memory" | "postgres" (postgres = 重启不失忆)
    agent_history_window: int = 20       # 单次传给 LLM 的最大历史消息条数（完整历史仍存 checkpointer）

    # Auth（JWT）—— 生产务必通过环境变量覆盖 JWT_SECRET 为强随机值（≥32 字节）
    jwt_secret: str = DEV_JWT_SECRET
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 10080      # 7 天

    # 注册时是否校验邮箱域名 MX 可投递性（查域名有无邮件服务器，拦编造域名如 hh.hh）。
    # 走 DNS，故测试需关闭（example.com 等无 MX 会被拒）；网络不稳时也可应急关闭。
    auth_check_email_deliverability: bool = True

    # Reranking
    rerank_enabled: bool = False
    rerank_fetch_k: int = 20

    # Chunking
    chunk_size: int = 500
    chunk_overlap: int = 50

    # 生成笔记时喂给 LLM 的正文上限（字符）。大文档全文塞进单次调用会超时/不稳，
    # 故截断到此预算保证调用快而稳；设 0 不截断。代价：超长文档笔记仅覆盖前段。
    notes_max_chars: int = 10000

    # File upload
    max_file_size_mb: int = 10

    # PDF 文本层乱码回退 OCR 的阈值：当解析结果中 /gidNNN 字形索引（内嵌字体缺
    # ToUnicode 映射的退化产物，常见于中文学术 PDF）占字符比例超过此值，
    # 就用强制全页 OCR 重解析。设 0 则禁用回退。
    parse_ocr_gid_threshold: float = 0.02

    # 文档处理任务时限（Celery）。需容纳首个 PDF 的 Docling 冷启动（首次下载版面模型，
    # 即便有缓存卷，第一次仍需下载）+ 大 PDF 的 CPU 解析。soft 先抛 SoftTimeLimitExceeded
    # 可被捕获置 FAILED；hard 是兜底硬杀。
    parse_task_soft_limit: int = 600
    parse_task_hard_limit: int = 660

    # 停滞文档对账：非终态停滞超过此秒数视为被中断（硬杀/OOM/重启），worker 启动时置 FAILED。
    # 必须 > parse_task_hard_limit，否则会把"还在跑的长任务"误判为僵尸。
    stuck_document_timeout: int = 900

    # Celery / Redis
    redis_url: str = "redis://localhost:6379/0"

    # Rate Limiting
    rate_limit_enabled: bool = True
    rate_limit_requests: int = 60   # max requests per window
    rate_limit_window: int = 60     # window size in seconds

    # LLM Resilience
    llm_timeout: float = 30.0
    llm_max_retries: int = 3
    embedding_timeout: float = 10.0
    embedding_max_retries: int = 3

    # Service backends — "local" uses in-process OpenAI client, "remote" calls model-service
    llm_backend: str = "local"          # "local" | "remote"
    embedding_backend: str = "local"    # "local" | "remote"
    model_service_url: str = "http://localhost:8009"

    # Logging
    log_level: str = "INFO"

    # File storage — uploaded files saved here for the worker to read
    storage_path: str = "storage"

    # Read .env
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # 忽略 .env 中未在 Settings 定义的字段
    )


# 让其他模块只需要 from app.core.config import settings 就能使用
settings = Settings()   # 保证 性能和一致性 -> 其余模块使用的都是同一个 Settings
