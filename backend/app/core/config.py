from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    app_name: str = "UI自动化脚本 API"
    app_env: str = "dev"
    database_url: str = "sqlite:///./app.db"
    run_scripts_dir: str = "./runtime/scripts"
    run_logs_dir: str = "./runtime/logs"
    run_command_prefix: str = "npx midscene"
    report_root_dir: str = "./midscene_run/report"
    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model_name: str = ""
    llm_timeout_sec: int = 60
    llm_generation_system_prompt: str = ""
    llm_generation_system_prompt_file: str = ""
    midscene_model_base_url: str = ""
    midscene_model_api_key: str = ""
    midscene_model_name: str = ""
    midscene_model_family: str = ""

    model_config = SettingsConfigDict(
        env_file=(str(BACKEND_ROOT / ".env"), ".env"),
        extra="ignore",
    )


settings = Settings()
