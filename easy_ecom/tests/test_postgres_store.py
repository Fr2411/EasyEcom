from easy_ecom.core.config import Settings
from easy_ecom.data.repos.postgres.products_stock_repo import ProductsPostgresRepo
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


def test_init_postgres_schema_and_products_repo_roundtrip(monkeypatch, tmp_path):
    sqlite_path = tmp_path / "store.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+pysqlite:///{sqlite_path}")

    engine = build_postgres_engine(Settings())
    init_postgres_schema(engine)
    repo = ProductsPostgresRepo(build_session_factory(engine))

    repo.append(
        {
            "product_id": "p-1",
            "client_id": "c-1",
            "supplier": "supplier",
            "product_name": "product",
            "category": "general",
            "prd_description": "",
            "prd_features_json": "",
            "default_selling_price": "100",
            "max_discount_pct": "10",
            "created_at": "2024-01-01T00:00:00Z",
            "is_active": "true",
            "is_parent": "true",
            "sizes_csv": "",
            "colors_csv": "",
            "others_csv": "",
            "parent_product_id": "",
        }
    )

    rows = repo.all()

    assert len(rows) == 1
    assert rows.iloc[0]["product_id"] == "p-1"
