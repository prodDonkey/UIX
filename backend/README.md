# Backend

## Quick Start

```bash
uv sync
cp .env.example .env
uv run uvicorn app.main:app --reload --port 8000
```

## Database

- 默认示例支持 SQLite 和 MySQL。
- 使用 MySQL 时请在 `.env` 设置：
  - `DATABASE_URL=mysql+pymysql://<user>:<password>@<host>:<port>/<db>?charset=utf8mb4`
- 首次切到新库会在启动时自动建表（`create_all`）。

## Notes
- M1 uses SQLAlchemy `create_all` on startup for quick bootstrap.
- Alembic is included in dependencies for later migration workflow.
