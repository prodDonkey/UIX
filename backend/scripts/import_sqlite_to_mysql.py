from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, inspect, text

TABLES_IN_ORDER = ["scripts", "script_versions", "runs"]


def _normalize_row(row: dict[str, Any]) -> dict[str, Any]:
    # MySQL 对空字符串/NULL 的容忍度更高，但这里保持原值，仅做 bytes 解码。
    normalized: dict[str, Any] = {}
    for key, value in row.items():
        if isinstance(value, bytes):
            normalized[key] = value.decode("utf-8", errors="ignore")
        else:
            normalized[key] = value
    return normalized


def _load_sqlite_rows(sqlite_engine, table_name: str) -> list[dict[str, Any]]:
    with sqlite_engine.connect() as conn:
        result = conn.execute(text(f"SELECT * FROM {table_name} ORDER BY id ASC"))
        return [_normalize_row(dict(row._mapping)) for row in result]


def _get_table_columns(engine, table_name: str) -> list[str]:
    inspector = inspect(engine)
    columns = inspector.get_columns(table_name)
    return [column["name"] for column in columns]


def _get_existing_ids(mysql_engine, table_name: str) -> set[int]:
    with mysql_engine.connect() as conn:
        result = conn.execute(text(f"SELECT id FROM {table_name}"))
        return {int(row[0]) for row in result}


def _insert_rows(mysql_engine, table_name: str, rows: list[dict[str, Any]], dry_run: bool) -> tuple[int, int]:
    if not rows:
        return (0, 0)

    mysql_columns = _get_table_columns(mysql_engine, table_name)
    sqlite_columns = list(rows[0].keys())
    common_columns = [name for name in sqlite_columns if name in mysql_columns]
    if "id" not in common_columns:
        raise RuntimeError(f"{table_name} 缺少 id 列，无法安全导入")

    existing_ids = _get_existing_ids(mysql_engine, table_name)

    insertable_rows = [row for row in rows if int(row["id"]) not in existing_ids]
    skipped_count = len(rows) - len(insertable_rows)
    if not insertable_rows:
        return (0, skipped_count)

    placeholders = ", ".join(f":{col}" for col in common_columns)
    column_sql = ", ".join(common_columns)
    stmt = text(f"INSERT INTO {table_name} ({column_sql}) VALUES ({placeholders})")

    payload = [{col: row.get(col) for col in common_columns} for row in insertable_rows]

    if dry_run:
        return (len(payload), skipped_count)

    with mysql_engine.begin() as conn:
        conn.execute(stmt, payload)

    return (len(payload), skipped_count)


def _count_rows(engine, table_name: str) -> int:
    with engine.connect() as conn:
        return int(conn.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar_one())


def main() -> int:
    parser = argparse.ArgumentParser(description="将 ui_demo 的 SQLite 数据导入 MySQL")
    parser.add_argument(
        "--sqlite-path",
        default="/Users/yaohongliang/work/liuyao/AI/UI/ui_demo/backend/app.db",
        help="SQLite 文件路径",
    )
    parser.add_argument(
        "--mysql-url",
        required=True,
        help="MySQL SQLAlchemy URL，例如 mysql+pymysql://user:pass@host:3306/ui_demo?charset=utf8mb4",
    )
    parser.add_argument("--dry-run", action="store_true", help="仅预演，不写入")

    args = parser.parse_args()

    sqlite_path = Path(args.sqlite_path).expanduser().resolve()
    if not sqlite_path.exists():
        raise FileNotFoundError(f"SQLite 文件不存在: {sqlite_path}")

    sqlite_engine = create_engine(f"sqlite:///{sqlite_path}")
    mysql_engine = create_engine(args.mysql_url, pool_pre_ping=True)

    print("[import] sqlite:", sqlite_path)
    print("[import] mysql:", args.mysql_url)
    print("[import] dry_run:", args.dry_run)

    for table in TABLES_IN_ORDER:
        # 预检查表存在
        _get_table_columns(sqlite_engine, table)
        _get_table_columns(mysql_engine, table)

    total_inserted = 0
    total_skipped = 0

    for table in TABLES_IN_ORDER:
        src_rows = _load_sqlite_rows(sqlite_engine, table)
        before = _count_rows(mysql_engine, table)
        inserted, skipped = _insert_rows(mysql_engine, table, src_rows, args.dry_run)
        after = _count_rows(mysql_engine, table) if not args.dry_run else before + inserted

        total_inserted += inserted
        total_skipped += skipped

        print(
            f"[import] table={table} src={len(src_rows)} before={before} inserted={inserted} skipped={skipped} after={after}"
        )

    print(f"[import] done inserted={total_inserted}, skipped={total_skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
