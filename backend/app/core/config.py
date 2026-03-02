from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "UI自动化脚本 API"
    app_env: str = "dev"
    database_url: str = "sqlite:///./app.db"
    run_scripts_dir: str = "./runtime/scripts"
    run_logs_dir: str = "./runtime/logs"
    run_command_prefix: str = "npx midscene"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
