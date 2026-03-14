from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from easy_ecom.core.config import Settings
from easy_ecom.core.ids import new_uuid
from easy_ecom.data.store.postgres import init_postgres_schema
from easy_ecom.data.store.postgres_db import build_postgres_engine, build_session_factory
from easy_ecom.data.store.postgres_models import ClientModel, RoleModel, UserModel, UserRoleModel
from easy_ecom.data.store.postgres_table_store import PostgresTableStore
from easy_ecom.data.store.schema import ROLES_SEED


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
    session_factory = build_session_factory(engine)

    with session_factory() as session:
        for role in ROLES_SEED:
            if session.execute(select(RoleModel).where(RoleModel.role_code == role["role_code"])).scalar_one_or_none() is None:
                session.add(RoleModel(**role))
        session.commit()

    return SqliteRuntime(
        settings=settings,
        store=store,
        session_factory=session_factory,
    )


def seed_auth_user(
    session_factory: sessionmaker[Session],
    *,
    user_id: str = "11111111-1111-1111-1111-111111111111",
    client_id: str = "22222222-2222-2222-2222-222222222222",
    name: str = "User One",
    email: str = "u1@example.com",
    password: str = "",
    password_hash: str = "",
    is_active: bool = True,
    role_code: str = "SUPER_ADMIN",
) -> None:
    with session_factory() as session:
        existing_client = session.execute(
            select(ClientModel).where(ClientModel.client_id == client_id)
        ).scalar_one_or_none()
        if existing_client is None:
            session.add(
                ClientModel(
                    client_id=client_id,
                    slug=f"client-{client_id.split('-')[0]}",
                    business_name="Client One",
                    owner_name="Owner",
                    email="owner@example.com",
                    currency_code="USD",
                    currency_symbol="$",
                    timezone="UTC",
                    status="active",
                )
            )

        existing_role = session.execute(
            select(RoleModel).where(RoleModel.role_code == role_code)
        ).scalar_one_or_none()
        if existing_role is None:
            session.add(RoleModel(role_code=role_code, role_name=role_code, description=role_code))

        session.add(
            UserModel(
                user_id=user_id,
                client_id=client_id,
                name=name,
                email=email.lower(),
                password=password,
                password_hash=password_hash,
                is_active=is_active,
            )
        )
        session.add(UserRoleModel(user_id=user_id, role_code=role_code))
        session.commit()
