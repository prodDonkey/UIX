from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_ROOT.parent


class Settings(BaseSettings):
    app_name: str = "UI自动化脚本 API"
    app_env: str = "dev"
    database_url: str
    db_pool_size: int = 20
    db_max_overflow: int = 40
    db_pool_timeout_sec: int = 30
    scene_http_timeout_sec: float = 30.0
    # 兼容 getresult-flow.ts 这类外部脚本里已有的变量配置，给场景执行提供兜底值。
    getresult_cookie: str | None = None
    getresult_uid: str | None = None
    getresult_address_id: str | None = None
    getresult_appointment_time: str | None = None

    model_config = SettingsConfigDict(
        env_file=(str(PROJECT_ROOT / ".env"),),
        extra="ignore",
    )


settings = Settings()
