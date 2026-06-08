from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "model-service"
    app_version: str = "0.1.0"
    host: str = "0.0.0.0"
    port: int = 8009
    log_level: str = "INFO"

    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4o-mini"
    embedding_model: str = "text-embedding-3-small"

    llm_timeout: float = 30.0
    llm_max_retries: int = 3
    embedding_timeout: float = 10.0
    embedding_max_retries: int = 3

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()
