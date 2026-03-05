from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from app.core.config import settings

is_sqlite = settings.database_url.startswith("sqlite")
engine_kwargs: dict = {
    "connect_args": {"check_same_thread": False} if is_sqlite else {},
    "pool_pre_ping": not is_sqlite,
}

if not is_sqlite:
    # MySQL 场景启用更大的连接池，降低并发请求 + 后台任务时的池耗尽风险。
    engine_kwargs.update(
        {
            "pool_size": settings.db_pool_size,
            "max_overflow": settings.db_max_overflow,
            "pool_timeout": settings.db_pool_timeout_sec,
        }
    )

engine = create_engine(settings.database_url, **engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
