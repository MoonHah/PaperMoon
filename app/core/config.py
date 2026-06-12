from pydantic_settings import BaseSettings, SettingsConfigDict


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

    # Agent
    agent_backend: str = "handwritten"   # "handwritten" | "langgraph"

    # Chunking
    chunk_size: int = 500
    chunk_overlap: int = 50

    # File upload
    max_file_size_mb: int = 10

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
