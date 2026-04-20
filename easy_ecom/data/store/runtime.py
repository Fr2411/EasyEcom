from __future__ import annotations

from easy_ecom.core.config import Settings
from easy_ecom.data.store.postgres import build_postgres_engine, init_postgres_schema
from easy_ecom.data.store.postgres_db import Engine


def build_runtime_engine(settings: Settings) -> Engine:
    engine = build_postgres_engine(settings)
    if settings.should_auto_create_schema:
        init_postgres_schema(engine)
    return engine
