from __future__ import annotations

from dataclasses import dataclass

from easy_ecom.core.config import Settings
from easy_ecom.data.repos.base import TabularRepo
from easy_ecom.data.repos.csv.inventory_repo import InventoryTxnRepo
from easy_ecom.data.repos.csv.product_variants_repo import ProductVariantsRepo
from easy_ecom.data.repos.csv.products_repo import ProductsRepo
from easy_ecom.data.repos.postgres.products_stock_repo import (
    InventoryTxnPostgresRepo,
    ProductsPostgresRepo,
    ProductVariantsPostgresRepo,
)
from easy_ecom.data.store.csv_store import CsvStore
from easy_ecom.data.store.postgres import (
    build_postgres_engine,
    build_session_factory,
    init_postgres_schema,
)


@dataclass(frozen=True)
class ProductStockRepos:
    products: TabularRepo
    product_variants: TabularRepo
    inventory_txn: TabularRepo


def build_product_stock_repos(settings: Settings, csv_store: CsvStore) -> ProductStockRepos:
    if settings.storage_backend.strip().lower() == "postgres":
        engine = build_postgres_engine(settings)
        init_postgres_schema(engine)
        session_factory = build_session_factory(engine)
        return ProductStockRepos(
            products=ProductsPostgresRepo(session_factory),
            product_variants=ProductVariantsPostgresRepo(session_factory),
            inventory_txn=InventoryTxnPostgresRepo(session_factory),
        )

    return ProductStockRepos(
        products=ProductsRepo(csv_store),
        product_variants=ProductVariantsRepo(csv_store),
        inventory_txn=InventoryTxnRepo(csv_store),
    )
