from __future__ import annotations

import pandas as pd

from easy_ecom.scripts.import_products_stock_to_postgres import (
    IMPORT_ORDER,
    _build_entity_rows,
    validate_counts,
)


def test_build_entity_rows_is_deterministic_and_unique_per_client() -> None:
    products = pd.DataFrame(
        [
            {"client_id": "c-1", "category": "Tea", "created_at": "2024-01-01"},
            {"client_id": "c-1", "category": "tea", "created_at": "2024-01-02"},
            {"client_id": "c-1", "category": "Coffee", "created_at": "2024-01-03"},
            {"client_id": "c-2", "category": "Tea", "created_at": "2024-01-01"},
            {"client_id": "c-2", "category": "", "created_at": "2024-01-02"},
        ]
    )

    categories = _build_entity_rows(products, "category", "category_id", "cat")

    assert len(categories) == 3
    assert categories["name"].tolist() == ["Coffee", "Tea", "Tea"]
    assert categories["category_id"].nunique() == 3


def test_validate_counts_flags_mismatches() -> None:
    class _Repo:
        def __init__(self, count: int):
            self._count = count

        def all(self) -> pd.DataFrame:
            return pd.DataFrame([{"id": i} for i in range(self._count)])

    source_rows = {table: pd.DataFrame([{"id": 1}, {"id": 2}]) for table in IMPORT_ORDER}
    target_repos = {table: _Repo(2) for table in IMPORT_ORDER}
    target_repos["inventory_txn"] = _Repo(1)

    ok, comparison = validate_counts(
        type("Context", (), {"source_rows": source_rows, "target_repos": target_repos})(),
        printer=lambda _: None,
    )

    assert not ok
    assert comparison["clients"] == (2, 2)
    assert comparison["inventory_txn"] == (2, 1)
