from __future__ import annotations

from pathlib import Path

from sqlalchemy import Engine, text


MIGRATIONS_TABLE = "schema_migrations"
MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "migrations" / "versions"


def _ensure_migrations_table(engine: Engine) -> None:
    statement = f"""
    CREATE TABLE IF NOT EXISTS {MIGRATIONS_TABLE} (
        version VARCHAR(255) PRIMARY KEY,
        applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """
    if engine.dialect.name == "sqlite":
        statement = f"""
        CREATE TABLE IF NOT EXISTS {MIGRATIONS_TABLE} (
            version TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    with engine.begin() as conn:
        conn.execute(text(statement))


def applied_migrations(engine: Engine) -> set[str]:
    _ensure_migrations_table(engine)
    with engine.begin() as conn:
        rows = conn.execute(text(f"SELECT version FROM {MIGRATIONS_TABLE}")).all()
    return {str(row[0]) for row in rows}


def apply_sql_migrations(engine: Engine, migrations_dir: Path | None = None) -> list[str]:
    if engine.dialect.name == "sqlite":
        return []

    target_dir = migrations_dir or MIGRATIONS_DIR
    _ensure_migrations_table(engine)
    already_applied = applied_migrations(engine)
    applied_now: list[str] = []

    for migration_path in sorted(target_dir.glob("*.sql")):
        version = migration_path.stem
        if version in already_applied:
            continue

        sql = migration_path.read_text(encoding="utf-8").strip()
        if not sql:
            continue

        raw_connection = engine.raw_connection()
        try:
            cursor = raw_connection.cursor()
            cursor.execute(sql)
            cursor.execute(
                f"INSERT INTO {MIGRATIONS_TABLE} (version) VALUES (%s)",
                (version,),
            )
            raw_connection.commit()
            applied_now.append(version)
        except Exception:
            raw_connection.rollback()
            raise
        finally:
            raw_connection.close()

    return applied_now
