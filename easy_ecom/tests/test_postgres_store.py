from sqlalchemy import text

from easy_ecom.core.config import Settings
from easy_ecom.data.store.postgres import init_postgres_schema
from easy_ecom.data.store.postgres_db import build_postgres_engine, build_session_factory


def test_postgres_engine_and_session_factory(monkeypatch, tmp_path):
    sqlite_path = tmp_path / "init.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+pysqlite:///{sqlite_path}")

    settings = Settings()
    engine = build_postgres_engine(settings)
    session_factory = build_session_factory(engine)

    with session_factory() as session:
        assert session.bind is engine


def test_init_postgres_schema_creates_auth_core_tables(monkeypatch, tmp_path):
    sqlite_path = tmp_path / "store.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+pysqlite:///{sqlite_path}")

    engine = build_postgres_engine(Settings())
    init_postgres_schema(engine)
    session_factory = build_session_factory(engine)

    with session_factory() as session:
        tables = {
            row[0]
            for row in session.execute(
                text("SELECT name FROM sqlite_master WHERE type='table'")
            ).all()
        }

    assert {"clients", "users", "roles", "user_roles"}.issubset(tables)
