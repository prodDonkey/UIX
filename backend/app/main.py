import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text

from app.api.scenes import router as scenes_router
from app.api.generate import router as generate_router
from app.api.runs import router as runs_router
from app.api.scripts import router as scripts_router
from app.core.config import settings
from app.core.database import Base, engine
from app.models import run, scene, scene_script, scene_task_item, script, script_version  # noqa: F401

logger = logging.getLogger("uvicorn.error")

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _ensure_runs_columns() -> None:
    inspector = inspect(engine)
    try:
        existing_columns = {column["name"] for column in inspector.get_columns("runs")}
    except Exception:  # noqa: BLE001
        return

    expected_columns = {
        "scene_id": "INTEGER",
        "scene_name_snapshot": "VARCHAR(128)",
        "total_tokens": "INTEGER",
        "current_task": "TEXT",
        "current_action": "TEXT",
        "progress_json": "TEXT",
        "request_id": "TEXT",
        "script_name_snapshot": "VARCHAR(128)",
        "script_content_snapshot": "TEXT",
        "script_updated_at_snapshot": "DATETIME",
        "remark": "TEXT",
        "is_starred": "BOOLEAN NOT NULL DEFAULT 0",
    }
    missing_columns = {name: ddl for name, ddl in expected_columns.items() if name not in existing_columns}
    if not missing_columns:
        return

    with engine.begin() as connection:
        for column_name, ddl_type in missing_columns.items():
            connection.execute(text(f"ALTER TABLE runs ADD COLUMN {column_name} {ddl_type}"))
            logger.info("已自动补充 runs.%s 字段", column_name)


@app.on_event("startup")
def startup() -> None:
    Base.metadata.create_all(bind=engine)
    _ensure_runs_columns()
    logger.info(
        "后端已启动：环境=%s 数据库=%s 模型已配置=%s 模型名=%s 基础地址=%s",
        settings.app_env,
        settings.database_url,
        bool(settings.llm_api_key or settings.midscene_model_api_key),
        settings.llm_model_name or settings.midscene_model_name or "(empty)",
        settings.llm_base_url or settings.midscene_model_base_url or "(empty)",
    )


@app.on_event("shutdown")
def shutdown() -> None:
    logger.info("后端已停止")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(scripts_router)
app.include_router(scenes_router)
app.include_router(generate_router)
app.include_router(runs_router)
