# Backend

## Quick Start

```bash
uv sync
cp .env.example .env
uv run uvicorn app.main:app --reload --port 8000
```

## Database

- 在 `.env` 中设置 MySQL 连接串：
  - `DATABASE_URL=mysql+pymysql://<user>:<password>@<host>:<port>/<db>?charset=utf8mb4`
- 首次切到新库会在启动时自动建表（`create_all`）。
- 集成测试请使用隔离库，并通过 `TEST_DATABASE_URL` 显式传入。

## Notes
- M1 uses SQLAlchemy `create_all` on startup for quick bootstrap.
- Alembic is included in dependencies for later migration workflow.
