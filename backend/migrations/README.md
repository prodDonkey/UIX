# Migrations

M1 uses `Base.metadata.create_all` for bootstrap.

For M2+, initialize Alembic:

```bash
uv run alembic init migrations
```
