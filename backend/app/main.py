import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.scenes import router as scenes_router
from app.api.scripts import router as scripts_router
from app.core.config import settings
from app.core.database import Base, engine
from app.models import scene, scene_script, scene_task_item, script, script_version  # noqa: F401

logger = logging.getLogger("uvicorn.error")

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    Base.metadata.create_all(bind=engine)
    logger.info(
        "后端已启动：环境=%s 数据库=%s",
        settings.app_env,
        settings.database_url,
    )


@app.on_event("shutdown")
def shutdown() -> None:
    logger.info("后端已停止")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(scripts_router)
app.include_router(scenes_router)
