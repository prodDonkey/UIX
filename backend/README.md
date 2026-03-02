# Backend

## Quick Start

```bash
uv sync
cp .env.example .env
uv run uvicorn app.main:app --reload --port 8000
```

## Notes
- M1 uses SQLAlchemy `create_all` on startup for quick bootstrap.
- Alembic is included in dependencies for later migration workflow.
