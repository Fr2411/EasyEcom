from __future__ import annotations

from easy_ecom.core.config import Settings
from easy_ecom.data.store.postgres import build_postgres_engine, init_postgres_schema
from easy_ecom.data.store.postgres_db import Engine
from easy_ecom.data.store.postgres_table_store import PostgresTableStore
from easy_ecom.data.store.tabular_store import TabularStore


def build_runtime_engine(settings: Settings) -> Engine:
    engine = build_postgres_engine(settings)
    init_postgres_schema(engine)
    return engine


def build_runtime_store(settings: Settings, engine: Engine | None = None) -> TabularStore:
    return PostgresTableStore(engine or build_runtime_engine(settings))
