from __future__ import annotations

from sqlalchemy import Engine

from easy_ecom.data.store import postgres_models  # noqa: F401
from easy_ecom.data.store.postgres_db import Base, build_postgres_engine, build_session_factory


def init_postgres_schema(engine: Engine) -> None:
    Base.metadata.create_all(bind=engine)
