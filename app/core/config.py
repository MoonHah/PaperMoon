from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "PaperMoon"
    app_version: str = "0.1.0"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8015

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


# 让其他模块只需要 from app.core.config import settings 就能使用
settings = Settings()   # 保证 性能和一致性 -> 其余模块使用的都是同一个 Settings