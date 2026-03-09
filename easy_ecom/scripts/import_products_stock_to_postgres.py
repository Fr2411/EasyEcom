from __future__ import annotations

import argparse
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import pandas as pd

from easy_ecom.core.config import Settings
from easy_ecom.data.repos.csv.clients_repo import ClientsRepo
from easy_ecom.data.repos.csv.inventory_repo import InventoryTxnRepo
from easy_ecom.data.repos.csv.product_variants_repo import ProductVariantsRepo
from easy_ecom.data.repos.csv.products_repo import ProductsRepo
from easy_ecom.data.repos.csv.users_repo import UsersRepo
from easy_ecom.data.repos.postgres.products_stock_repo import (
    CategoriesPostgresRepo,
    ClientsPostgresRepo,
    InventoryTxnPostgresRepo,
    ProductsPostgresRepo,
    ProductVariantsPostgresRepo,
    SuppliersPostgresRepo,
    UsersPostgresRepo,
)
from easy_ecom.data.store import postgres_models  # noqa: F401
from easy_ecom.data.store.csv_store import CsvStore
from easy_ecom.data.store.postgres import (
    build_postgres_engine,
    build_session_factory,
    init_postgres_schema,
)

IMPORT_ORDER: tuple[str, ...] = (
    "clients",
    "users",
    "categories",
    "suppliers",
    "products",
    "product_variants",
    "inventory_txn",
)

TABLE_KEY_COLUMNS: dict[str, str] = {
    "clients": "client_id",
    "users": "user_id",
    "categories": "category_id",
    "suppliers": "supplier_id",
    "products": "product_id",
    "product_variants": "variant_id",
    "inventory_txn": "txn_id",
}


@dataclass(frozen=True)
class ImportContext:
    source_rows: dict[str, pd.DataFrame]
    target_repos: dict[str, object]


def _normalize(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=columns)
    normalized = df.copy().fillna("")
    for column in columns:
        if column not in normalized.columns:
            normalized[column] = ""
    return normalized[columns].astype(str)


def _stable_entity_id(prefix: str, client_id: str, name: str) -> str:
    canonical = f"{client_id.strip().lower()}::{name.strip().lower()}"
    digest = uuid.uuid5(uuid.NAMESPACE_DNS, canonical)
    return f"{prefix}-{digest.hex[:16]}"


def _build_entity_rows(
    products: pd.DataFrame,
    value_column: str,
    id_column: str,
    prefix: str,
) -> pd.DataFrame:
    if products.empty:
        return pd.DataFrame(
            columns=[id_column, "client_id", "name", "description", "created_at", "is_active"]
        )

    scoped = products[["client_id", value_column, "created_at"]].copy().fillna("")
    scoped[value_column] = scoped[value_column].astype(str).str.strip()
    scoped = scoped[scoped[value_column] != ""]
    if scoped.empty:
        return pd.DataFrame(
            columns=[id_column, "client_id", "name", "description", "created_at", "is_active"]
        )

    scoped["name_ci"] = scoped[value_column].str.lower()
    scoped = scoped.sort_values(["client_id", "name_ci", "created_at"], kind="stable")
    deduped = scoped.drop_duplicates(subset=["client_id", "name_ci"], keep="first").copy()
    deduped[id_column] = deduped.apply(
        lambda row: _stable_entity_id(prefix, str(row["client_id"]), str(row[value_column])), axis=1
    )
    deduped["name"] = deduped[value_column]
    deduped["description"] = ""
    deduped["is_active"] = "true"
    return deduped[[id_column, "client_id", "name", "description", "created_at", "is_active"]]


def _load_optional_csv(
    store: CsvStore, table_name: str, required_columns: list[str]
) -> pd.DataFrame:
    path = store.file_path(table_name)
    if not path.exists():
        return pd.DataFrame(columns=required_columns)
    return _normalize(store.read(table_name), required_columns)


def build_csv_snapshot(csv_store: CsvStore) -> dict[str, pd.DataFrame]:
    clients = ClientsRepo(csv_store).all()
    users = UsersRepo(csv_store).all()
    products = ProductsRepo(csv_store).all()
    product_variants = ProductVariantsRepo(csv_store).all()
    inventory_txn = InventoryTxnRepo(csv_store).all()

    categories = _load_optional_csv(
        csv_store,
        "categories.csv",
        ["category_id", "client_id", "name", "description", "created_at", "is_active"],
    )
    if categories.empty:
        categories = _build_entity_rows(products, "category", "category_id", "cat")

    suppliers = _load_optional_csv(
        csv_store,
        "suppliers.csv",
        [
            "supplier_id",
            "client_id",
            "name",
            "contact_name",
            "phone",
            "email",
            "created_at",
            "is_active",
        ],
    )
    if suppliers.empty:
        suppliers = _build_entity_rows(products, "supplier", "supplier_id", "sup")
        suppliers["contact_name"] = ""
        suppliers["phone"] = ""
        suppliers["email"] = ""
        suppliers = suppliers[
            [
                "supplier_id",
                "client_id",
                "name",
                "contact_name",
                "phone",
                "email",
                "created_at",
                "is_active",
            ]
        ]

    return {
        "clients": _normalize(
            clients,
            [
                "client_id",
                "business_name",
                "owner_name",
                "phone",
                "email",
                "address",
                "currency_code",
                "currency_symbol",
                "website_url",
                "facebook_url",
                "instagram_url",
                "whatsapp_number",
                "created_at",
                "status",
                "notes",
            ],
        ),
        "users": _normalize(
            users,
            ["user_id", "client_id", "name", "email", "password", "is_active", "created_at"],
        ),
        "categories": _normalize(
            categories,
            ["category_id", "client_id", "name", "description", "created_at", "is_active"],
        ),
        "suppliers": _normalize(
            suppliers,
            [
                "supplier_id",
                "client_id",
                "name",
                "contact_name",
                "phone",
                "email",
                "created_at",
                "is_active",
            ],
        ),
        "products": _normalize(
            products,
            [
                "product_id",
                "client_id",
                "supplier",
                "product_name",
                "category",
                "prd_description",
                "prd_features_json",
                "default_selling_price",
                "max_discount_pct",
                "created_at",
                "is_active",
                "is_parent",
                "sizes_csv",
                "colors_csv",
                "others_csv",
                "parent_product_id",
            ],
        ),
        "product_variants": _normalize(
            product_variants,
            [
                "variant_id",
                "client_id",
                "parent_product_id",
                "variant_name",
                "size",
                "color",
                "other",
                "sku_code",
                "default_selling_price",
                "max_discount_pct",
                "is_active",
                "created_at",
            ],
        ),
        "inventory_txn": _normalize(
            inventory_txn,
            [
                "txn_id",
                "client_id",
                "timestamp",
                "user_id",
                "txn_type",
                "product_id",
                "product_name",
                "qty",
                "unit_cost",
                "total_cost",
                "supplier_snapshot",
                "note",
                "source_type",
                "source_id",
                "lot_id",
            ],
        ),
    }


def build_import_context(settings: Settings) -> ImportContext:
    csv_store = CsvStore(settings.data_dir)
    source_rows = build_csv_snapshot(csv_store)

    engine = build_postgres_engine(settings)
    init_postgres_schema(engine)
    session_factory = build_session_factory(engine)

    target_repos = {
        "clients": ClientsPostgresRepo(session_factory),
        "users": UsersPostgresRepo(session_factory),
        "categories": CategoriesPostgresRepo(session_factory),
        "suppliers": SuppliersPostgresRepo(session_factory),
        "products": ProductsPostgresRepo(session_factory),
        "product_variants": ProductVariantsPostgresRepo(session_factory),
        "inventory_txn": InventoryTxnPostgresRepo(session_factory),
    }
    return ImportContext(source_rows=source_rows, target_repos=target_repos)


def run_import(context: ImportContext, printer: Callable[[str], None] = print) -> dict[str, int]:
    for table in IMPORT_ORDER:
        context.target_repos[table].save(context.source_rows[table])

    counts = {table: len(context.target_repos[table].all()) for table in IMPORT_ORDER}
    printer("Postgres row counts after import:")
    for table in IMPORT_ORDER:
        printer(f"- {table}: {counts[table]}")
    return counts


def validate_counts(
    context: ImportContext, printer: Callable[[str], None] = print
) -> tuple[bool, dict[str, tuple[int, int]], dict[str, tuple[int, int]]]:
    comparison: dict[str, tuple[int, int]] = {}
    key_comparison: dict[str, tuple[int, int]] = {}
    all_match = True
    printer("CSV vs Postgres row-count validation:")
    for table in IMPORT_ORDER:
        csv_count = len(context.source_rows[table])
        pg_count = len(context.target_repos[table].all())
        comparison[table] = (csv_count, pg_count)
        status = "OK" if csv_count == pg_count else "MISMATCH"
        if status == "MISMATCH":
            all_match = False
        printer(f"- {table}: csv={csv_count}, postgres={pg_count} [{status}]")

    printer("CSV vs Postgres key-count validation:")
    for table in IMPORT_ORDER:
        key_column = TABLE_KEY_COLUMNS[table]
        csv_keys = set(context.source_rows[table][key_column].astype(str))
        pg_keys = set(context.target_repos[table].all()[key_column].astype(str))
        csv_key_count = len(csv_keys)
        pg_key_count = len(pg_keys)
        key_comparison[table] = (csv_key_count, pg_key_count)
        status = "OK" if csv_key_count == pg_key_count else "MISMATCH"
        if status == "MISMATCH":
            all_match = False
        printer(f"- {table} ({key_column}): csv={csv_key_count}, postgres={pg_key_count} [{status}]")

    return all_match, comparison, key_comparison


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="One-time Products & Stock CSV -> Postgres importer with deterministic validation"
    )
    parser.add_argument(
        "--data-dir",
        default=None,
        help="Override CSV data directory (defaults to Settings.data_dir)",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Skip import and validate row counts only",
    )
    parser.add_argument(
        "--skip-validate",
        action="store_true",
        help="Skip validation after import",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    settings = Settings()
    if args.data_dir:
        settings = Settings(data_dir=Path(args.data_dir))

    context = build_import_context(settings)

    if args.validate_only:
        ok, _, _ = validate_counts(context)
        return 0 if ok else 1

    run_import(context)
    if args.skip_validate:
        return 0

    ok, _, _ = validate_counts(context)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
