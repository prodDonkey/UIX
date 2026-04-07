from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    app_name: str = "UI自动化脚本 API"
    app_env: str = "dev"
    database_url: str
    db_pool_size: int = 20
    db_max_overflow: int = 40
    db_pool_timeout_sec: int = 30
    scene_http_timeout_sec: float = 30.0

    model_config = SettingsConfigDict(
        env_file=(str(BACKEND_ROOT / ".env"), ".env"),
        extra="ignore",
    )


settings = Settings()
