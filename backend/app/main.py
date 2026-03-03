import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.generate import router as generate_router
from app.api.runs import router as runs_router
from app.api.scripts import router as scripts_router
from app.core.config import settings
from app.core.database import Base, engine
from app.models import run, script, script_version  # noqa: F401

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
app.include_router(generate_router)
app.include_router(runs_router)
