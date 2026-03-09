from __future__ import annotations

from easy_ecom.core.config import Settings
from easy_ecom.data.store.csv_store import CsvStore
from easy_ecom.data.store.postgres import build_postgres_engine, init_postgres_schema
from easy_ecom.data.store.postgres_table_store import PostgresTableStore
from easy_ecom.data.store.tabular_store import TabularStore


def build_runtime_store(settings: Settings) -> TabularStore:
    engine = build_postgres_engine(settings)
    init_postgres_schema(engine)
    return PostgresTableStore(engine)


def build_csv_store(settings: Settings) -> CsvStore:
    return CsvStore(settings.data_dir)
