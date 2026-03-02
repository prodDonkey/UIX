from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.scripts import router as scripts_router
from app.core.config import settings
from app.core.database import Base, engine
from app.models import run, script, script_version  # noqa: F401

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


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(scripts_router)
