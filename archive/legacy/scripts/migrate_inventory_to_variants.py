from __future__ import annotations

from easy_ecom.core.config import settings
from easy_ecom.data.repos.csv.inventory_repo import InventoryTxnRepo
from easy_ecom.data.repos.csv.product_variants_repo import ProductVariantsRepo
from easy_ecom.data.store.csv_store import CsvStore


def run() -> int:
    store = CsvStore(settings.data_dir)
    repo = InventoryTxnRepo(store)
    variants = ProductVariantsRepo(store).all()
    txns = repo.all()
    if txns.empty or variants.empty:
        return 0
    defaults = variants.groupby("parent_product_id").first().reset_index().set_index("parent_product_id")["variant_id"].to_dict()
    updated = 0
    for idx, row in txns.iterrows():
        product_id = str(row.get("product_id", ""))
        if product_id in set(variants.get("variant_id", [])):
            continue
        if product_id in defaults:
            txns.loc[idx, "product_id"] = defaults[product_id]
            updated += 1
    repo.save(txns)
    return updated


if __name__ == "__main__":
    print(f"migrated_rows={run()}")
