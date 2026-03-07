from pathlib import Path

from easy_ecom.core.config import Settings
from easy_ecom.data.repos.csv.products_repo import ProductsRepo
from easy_ecom.data.repos.factory import build_product_stock_repos
from easy_ecom.data.repos.postgres.products_stock_repo import (
    InventoryTxnPostgresRepo,
    ProductsPostgresRepo,
    ProductVariantsPostgresRepo,
)
from easy_ecom.data.store.csv_store import CsvStore


def test_backend_selector_defaults_to_csv(monkeypatch):
    monkeypatch.delenv("STORAGE_BACKEND", raising=False)

    cfg = Settings()

    assert cfg.storage_backend == "CSV"


def test_backend_selector_returns_csv_repos_for_default(tmp_path: Path):
    cfg = Settings()
    repos = build_product_stock_repos(cfg, CsvStore(tmp_path))

    assert isinstance(repos.products, ProductsRepo)


def test_backend_selector_returns_postgres_repos(monkeypatch, tmp_path: Path):
    sqlite_path = tmp_path / "products_stock.db"
    monkeypatch.setenv("STORAGE_BACKEND", "POSTGRES")
    monkeypatch.setenv("POSTGRES_DSN", f"sqlite+pysqlite:///{sqlite_path}")
    cfg = Settings()

    repos = build_product_stock_repos(cfg, CsvStore(tmp_path / "csv"))

    assert isinstance(repos.products, ProductsPostgresRepo)
    assert isinstance(repos.product_variants, ProductVariantsPostgresRepo)
    assert isinstance(repos.inventory_txn, InventoryTxnPostgresRepo)
