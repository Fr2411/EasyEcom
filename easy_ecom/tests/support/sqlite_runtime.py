from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session, sessionmaker

from easy_ecom.core.config import Settings
from easy_ecom.data.store.postgres import init_postgres_schema
from easy_ecom.data.store.postgres_db import build_postgres_engine, build_session_factory
from easy_ecom.data.store.postgres_models import UserModel, UserRoleModel
from easy_ecom.data.store.postgres_table_store import PostgresTableStore


@dataclass(frozen=True)
class SqliteRuntime:
    settings: Settings
    store: PostgresTableStore
    session_factory: sessionmaker[Session]


def build_sqlite_runtime(tmp_path: Path, filename: str = "test.db") -> SqliteRuntime:
    settings = Settings(database_url=f"sqlite+pysqlite:///{tmp_path / filename}")
    engine = build_postgres_engine(settings)
    init_postgres_schema(engine)

    store = PostgresTableStore(engine)

    return SqliteRuntime(
        settings=settings,
        store=store,
        session_factory=build_session_factory(engine),
    )


def seed_auth_user(
    session_factory: sessionmaker[Session],
    *,
    user_id: str = "u1",
    client_id: str = "c1",
    name: str = "User One",
    email: str = "u1@example.com",
    password: str = "",
    password_hash: str = "",
    is_active: str = "true",
    role_code: str = "SUPER_ADMIN",
) -> None:
    with session_factory() as session:
        session.add(
            UserModel(
                user_id=user_id,
                client_id=client_id,
                name=name,
                email=email.lower(),
                password=password,
                password_hash=password_hash,
                is_active=is_active,
                created_at="",
            )
        )
        session.add(UserRoleModel(user_id=user_id, role_code=role_code))
        session.commit()
