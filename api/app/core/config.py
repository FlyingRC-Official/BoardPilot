from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "BoardPilot"
    environment: str = "local"
    storage_root: str = "storage"
    audit_log_path: str = ""
    database_url: str = "sqlite:///:memory:"
    redis_url: str = "redis://localhost:6379/0"
    llm_provider: str = "fake"
    embedding_provider: str = "fake"
    reranker_provider: str = "fake"
    ocr_provider: str = "fake"

    model_config = SettingsConfigDict(env_prefix="BOARDPILOT_")


settings = Settings()
