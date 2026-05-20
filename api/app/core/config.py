from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "BoardPilot"
    environment: str = Field("local", validation_alias=AliasChoices("BOARDPILOT_ENV", "BOARDPILOT_ENVIRONMENT"))
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    storage_root: str = "storage"
    audit_log_path: str = ""
    api_key: str = ""
    session_ttl_seconds: int = 86400
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    database_url: str = "sqlite:///:memory:"
    redis_url: str = "redis://localhost:6379/0"
    llm_provider: str = "fake"
    embedding_provider: str = "fake"
    reranker_provider: str = "fake"
    ocr_provider: str = "fake"

    model_config = SettingsConfigDict(env_prefix="BOARDPILOT_")


settings = Settings()
