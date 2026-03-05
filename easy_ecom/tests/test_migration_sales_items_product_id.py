from pathlib import Path

from easy_ecom.data.store.csv_store import CsvStore
from easy_ecom.data.store.schema import TABLE_SCHEMAS
from easy_ecom.scripts.migrate_sales_items_product_id import migrate


def setup_store(tmp_path: Path) -> CsvStore:
    store = CsvStore(tmp_path)
    for t, c in TABLE_SCHEMAS.items():
        store.ensure_table(t, c)
    return store


def test_migration_maps_product_name_to_uuid(tmp_path: Path):
    store = setup_store(tmp_path)
    store.append("products.csv", {"product_id": "11111111-1111-1111-1111-111111111111", "client_id": "c1", "supplier": "", "product_name": "Phone Case", "category": "", "prd_description": "", "prd_features_json": "{}", "default_selling_price": "10", "max_discount_pct": "5", "created_at": "", "is_active": "true"})
    store.append("sales_orders.csv", {"order_id": "o1", "client_id": "c1", "timestamp": "", "customer_id": "cu", "status": "confirmed", "subtotal": "10", "discount": "0", "tax": "0", "grand_total": "10", "note": ""})
    store.append("sales_order_items.csv", {"order_item_id": "i1", "order_id": "o1", "product_id": "Phone Case", "prd_description_snapshot": "", "qty": "1", "unit_selling_price": "10", "total_selling_price": "10"})

    updated = migrate(tmp_path)
    assert updated == 1

    items = store.read("sales_order_items.csv")
    assert items.iloc[0]["product_id"] == "11111111-1111-1111-1111-111111111111"
    assert items.iloc[0]["product_name_snapshot"] == "Phone Case"
