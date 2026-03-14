from __future__ import annotations

from easy_ecom.core.config import settings
from easy_ecom.data.store.migrations import apply_sql_migrations
from easy_ecom.data.store.postgres import init_postgres_schema
from easy_ecom.data.store.postgres_db import build_postgres_engine


def main() -> None:
    engine = build_postgres_engine(settings)
    if settings.is_sqlite:
        init_postgres_schema(engine)
        print("[migrate] sqlite schema created from SQLAlchemy models")
        return

    applied = apply_sql_migrations(engine)
    if applied:
        print(f"[migrate] applied: {', '.join(applied)}")
    else:
        print("[migrate] no pending migrations")


if __name__ == "__main__":
    main()
