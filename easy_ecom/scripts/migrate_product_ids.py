from __future__ import annotations

from pathlib import Path

import pandas as pd

from easy_ecom.core.ids import new_uuid
from easy_ecom.data.store.csv_store import CsvStore


def migrate(data_dir: Path) -> None:
    store = CsvStore(data_dir)
    products = store.read("products.csv")
    inv = store.read("inventory_txn.csv")
    items = store.read("sales_order_items.csv")

    if products.empty:
        print("No products to migrate")
        return

    mapping_rows: list[dict[str, str]] = []
    for (client_id, pname), group in products.groupby(["client_id", "product_name"], dropna=False):
        stable_id = group.iloc[0]["product_id"] or new_uuid()
        if not group.iloc[0]["product_id"]:
            products.loc[group.index, "product_id"] = stable_id
        mapping_rows.append({"client_id": client_id, "product_name": str(pname), "stable_product_id": stable_id})

    mapping = pd.DataFrame(mapping_rows)

    def resolve(client_id: str, product_id: str, product_name: str = "") -> str:
        hit = mapping[(mapping["client_id"] == client_id) & (mapping["product_name"].str.lower() == str(product_name).lower())]
        if hit.empty and "_LOT-" in str(product_id):
            guess = str(product_id).split("_LOT-", 1)[0].replace("_", " ")
            hit = mapping[(mapping["client_id"] == client_id) & (mapping["product_name"].str.lower() == guess.lower())]
        if not hit.empty:
            return str(hit.iloc[0]["stable_product_id"])
        return str(product_id)

    if not inv.empty:
        inv["product_id"] = inv.apply(lambda r: resolve(str(r["client_id"]), str(r["product_id"]), str(r.get("product_name", ""))), axis=1)
        store.write("inventory_txn.csv", inv)
    if not items.empty:
        orders = store.read("sales_orders.csv")
        order_clients = orders[["order_id", "client_id"]] if not orders.empty else pd.DataFrame(columns=["order_id", "client_id"])
        items = items.merge(order_clients, on="order_id", how="left")
        items["product_id"] = items.apply(lambda r: resolve(str(r.get("client_id", "")), str(r["product_id"])), axis=1)
        store.write("sales_order_items.csv", items.drop(columns=["client_id"], errors="ignore"))

    store.write("products.csv", products)
    print("Migration complete")


if __name__ == "__main__":
    migrate(Path("easy_ecom/data_files"))
