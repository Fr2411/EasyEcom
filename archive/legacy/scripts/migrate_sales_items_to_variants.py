from __future__ import annotations

from easy_ecom.core.config import settings
from easy_ecom.data.repos.csv.product_variants_repo import ProductVariantsRepo
from easy_ecom.data.repos.csv.products_repo import ProductsRepo
from easy_ecom.data.repos.csv.sales_repo import SalesOrderItemsRepo
from easy_ecom.data.store.csv_store import CsvStore


def run() -> int:
    store = CsvStore(settings.data_dir)
    items_repo = SalesOrderItemsRepo(store)
    products = ProductsRepo(store).all()
    variants = ProductVariantsRepo(store).all()
    items = items_repo.all()
    if items.empty or variants.empty or products.empty:
        return 0
    product_to_default = variants.groupby("parent_product_id").first().reset_index().set_index("parent_product_id")["variant_id"].to_dict()
    name_to_parent = products.set_index(products["product_name"].str.lower())["product_id"].to_dict()
    updated = 0
    for idx, row in items.iterrows():
        product_id = str(row.get("product_id", ""))
        if product_id in set(variants.get("variant_id", [])):
            continue
        parent_id = product_id if product_id in product_to_default else name_to_parent.get(product_id.lower())
        if not parent_id or parent_id not in product_to_default:
            continue
        items.loc[idx, "product_id"] = product_to_default[parent_id]
        updated += 1
    items_repo.save(items)
    return updated


if __name__ == "__main__":
    print(f"migrated_rows={run()}")
