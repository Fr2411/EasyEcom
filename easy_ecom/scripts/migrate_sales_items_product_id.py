from __future__ import annotations

import uuid
from pathlib import Path

from easy_ecom.data.store.csv_store import CsvStore


def is_uuid(value: str) -> bool:
    try:
        uuid.UUID(str(value))
        return True
    except Exception:
        return False


def migrate(data_dir: Path) -> int:
    store = CsvStore(data_dir)
    products = store.read("products.csv")
    items = store.read("sales_order_items.csv")
    orders = store.read("sales_orders.csv")
    if items.empty or products.empty or orders.empty:
        return 0

    if "product_name_snapshot" not in items.columns:
        items["product_name_snapshot"] = ""

    order_client = orders[["order_id", "client_id"]].drop_duplicates()
    work = items.merge(order_client, on="order_id", how="left")
    if "client_id" not in work.columns:
        work["client_id"] = ""
    if "client_id_x" in work.columns:
        work["client_id"] = work["client_id"].where(
            work["client_id"].astype(str).str.strip() != "", work["client_id_x"]
        )
    if "client_id_y" in work.columns:
        work["client_id"] = work["client_id"].where(
            work["client_id"].astype(str).str.strip() != "", work["client_id_y"]
        )
    updates = 0

    for i, row in work.iterrows():
        current = str(row.get("product_id", ""))
        if is_uuid(current):
            continue
        client_id = str(row.get("client_id", ""))
        match = products[
            (products["client_id"] == client_id)
            & (products["product_name"].astype(str).str.lower() == current.strip().lower())
        ]
        if match.empty:
            continue
        work.at[i, "product_name_snapshot"] = current
        work.at[i, "product_id"] = str(match.iloc[0]["product_id"])
        updates += 1

    if updates:
        store.write("sales_order_items.csv", work.drop(columns=["client_id"], errors="ignore"))
    return updates


if __name__ == "__main__":
    changed = migrate(Path("easy_ecom/data_files"))
    print(f"Migrated sales_order_items rows: {changed}")
