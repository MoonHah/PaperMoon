from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "PaperMoon"
    app_version: str = "0.1.0"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8008

    # Qdrant Vector Database
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "papermoon"
    vector_size: int = 1536

    # LLM
    llm_mode: str = "mock"               # "mock" | "openai"
    llm_model: str = "gpt-4o-mini"
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"

    # Embedding
    embedding_mode: str = "mock"         # "mock" | "openai"
    embedding_model: str = "text-embedding-3-small"

    # Chunking
    chunk_size: int = 500
    chunk_overlap: int = 50

    # File upload
    max_file_size_mb: int = 10

    # Read .env
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # 忽略 .env 中未在 Settings 定义的字段
    )


# 让其他模块只需要 from app.core.config import settings 就能使用
settings = Settings()   # 保证 性能和一致性 -> 其余模块使用的都是同一个 Settings