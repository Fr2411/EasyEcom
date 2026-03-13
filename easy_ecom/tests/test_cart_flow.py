from pathlib import Path

from easy_ecom.data.repos.csv.customers_repo import CustomersRepo
from easy_ecom.data.repos.csv.finance_repo import LedgerRepo
from easy_ecom.data.repos.csv.inventory_repo import InventoryTxnRepo
from easy_ecom.data.repos.csv.product_variants_repo import ProductVariantsRepo
from easy_ecom.data.repos.csv.products_repo import ProductsRepo
from easy_ecom.data.repos.csv.sales_repo import (
    InvoicesRepo,
    PaymentsRepo,
    SalesOrderItemsRepo,
    SalesOrdersRepo,
    ShipmentsRepo,
)
from easy_ecom.data.repos.csv.sequences_repo import SequencesRepo
from easy_ecom.domain.models.sales import SaleItem
from easy_ecom.domain.services.finance_service import FinanceService
from easy_ecom.domain.services.inventory_service import InventoryService, SequenceService
from easy_ecom.domain.services.sales_service import SalesService
from easy_ecom.tests.support.sqlite_runtime import build_sqlite_runtime


def setup_store(tmp_path: Path):
    store = build_sqlite_runtime(tmp_path, "cart_flow.db").store
    seq = SequenceService(SequencesRepo(store))
    inv = InventoryService(InventoryTxnRepo(store), seq)
    fin = FinanceService(LedgerRepo(store), InventoryTxnRepo(store))
    svc = SalesService(
        SalesOrdersRepo(store),
        SalesOrderItemsRepo(store),
        InvoicesRepo(store),
        ShipmentsRepo(store),
        PaymentsRepo(store),
        inv,
        seq,
        fin,
        ProductsRepo(store),
        CustomersRepo(store),
        variants_repo=ProductVariantsRepo(store),
    )
    return store, svc


def seed_common_data(store):
    ProductsRepo(store).append(
        {
            "product_id": "p1",
            "client_id": "c1",
            "supplier": "sup",
            "product_name": "Phone Case",
            "category": "General",
            "prd_description": "",
            "prd_features_json": "{}",
            "default_selling_price": "20",
            "max_discount_pct": "10",
            "created_at": "",
            "is_active": "true",
            "is_parent": "true",
            "sizes_csv": "",
            "colors_csv": "",
            "others_csv": "",
            "parent_product_id": "",
        }
    )
    ProductsRepo(store).append(
        {
            "product_id": "p2",
            "client_id": "c1",
            "supplier": "sup",
            "product_name": "Charger",
            "category": "General",
            "prd_description": "",
            "prd_features_json": "{}",
            "default_selling_price": "40",
            "max_discount_pct": "20",
            "created_at": "",
            "is_active": "true",
            "is_parent": "true",
            "sizes_csv": "",
            "colors_csv": "",
            "others_csv": "",
            "parent_product_id": "",
        }
    )
    ProductVariantsRepo(store).append(
        {
            "variant_id": "v1",
            "client_id": "c1",
            "parent_product_id": "p1",
            "variant_name": "Color:Red",
            "size": "",
            "color": "Red",
            "other": "",
            "sku_code": "sku1",
            "default_selling_price": "22",
            "max_discount_pct": "10",
            "is_active": "true",
            "created_at": "",
        }
    )
    CustomersRepo(store).append(
        {
            "customer_id": "cu1",
            "client_id": "c1",
            "created_at": "",
            "full_name": "Alice",
            "phone": "111",
            "email": "a@x.com",
            "whatsapp": "",
            "address_line1": "A1",
            "address_line2": "",
            "area": "",
            "city": "Dubai",
            "state": "",
            "postal_code": "",
            "country": "",
            "preferred_contact_channel": "",
            "marketing_opt_in": "false",
            "tags": "",
            "notes": "",
            "is_active": "true",
        }
    )


def test_create_and_reuse_customer_draft(tmp_path: Path):
    store, svc = setup_store(tmp_path)
    seed_common_data(store)
    first = svc.get_or_create_customer_draft("c1", "cu1")
    second = svc.get_or_create_customer_draft("c1", "cu1")
    third = svc.get_or_create_customer_draft("c1", "cu1", force_new=True)
    assert first == second
    assert third != first


def test_add_item_merges_same_product_line(tmp_path: Path):
    store, svc = setup_store(tmp_path)
    seed_common_data(store)
    order_id = svc.create_draft_order("c1", "cu1")
    line_1 = svc.add_item_to_draft(
        order_id, "c1", SaleItem(product_id="p1", qty=1, unit_selling_price=20)
    )
    line_2 = svc.add_item_to_draft(
        order_id, "c1", SaleItem(product_id="p1", qty=2, unit_selling_price=20)
    )
    items = svc.get_order_items(order_id)
    assert line_1 == line_2
    assert len(items) == 1
    assert float(items.iloc[0]["qty"]) == 3.0


def test_compute_totals_formula(tmp_path: Path):
    store, svc = setup_store(tmp_path)
    seed_common_data(store)
    order_id = svc.create_draft_order("c1", "cu1", discount=5, tax=2, delivery_cost=3)
    svc.add_item_to_draft(order_id, "c1", SaleItem(product_id="p1", qty=2, unit_selling_price=20))
    totals = svc.compute_order_totals(order_id)
    assert totals["subtotal"] == 40.0
    assert totals["discount"] == 5.0
    assert totals["tax"] == 2.0
    assert totals["delivery_cost"] == 3.0
    assert totals["grand_total"] == 40.0


def test_confirm_uses_grand_total_for_invoice_and_ledger(tmp_path: Path):
    store, svc = setup_store(tmp_path)
    seed_common_data(store)
    inv = InventoryService(InventoryTxnRepo(store), SequenceService(SequencesRepo(store)))
    inv.add_stock("c1", "p1", "p1", "Phone Case", 10, 5, "sup", "")
    order_id = svc.create_draft_order("c1", "cu1", discount=5, tax=2, delivery_cost=3)
    svc.add_item_to_draft(order_id, "c1", SaleItem(product_id="p1", qty=2, unit_selling_price=20))
    svc.confirm_order(order_id, {"client_id": "c1", "user_id": "u1"})

    invoice = InvoicesRepo(store).all().iloc[0]
    assert float(invoice["amount_due"]) == 40.0

    ledger = LedgerRepo(store).all()
    sales_entry = ledger[
        (ledger["entry_type"] == "earning") & (ledger["category"] == "Sales")
    ].iloc[0]
    assert float(sales_entry["amount"]) == 40.0


def test_empty_and_cancel_draft_behaviors(tmp_path: Path):
    store, svc = setup_store(tmp_path)
    seed_common_data(store)
    order_id = svc.create_draft_order("c1", "cu1")
    svc.add_item_to_draft(order_id, "c1", SaleItem(product_id="p1", qty=1, unit_selling_price=20))
    svc.empty_draft_order(order_id, "c1")
    assert svc.get_order_items(order_id).empty
    order = svc.get_order(order_id) or {}
    assert order.get("status") == "draft"
    assert svc.cancel_draft_order(order_id) is True
    assert svc.cancel_draft_order(order_id) is False


def test_variant_display_resolution(tmp_path: Path):
    store, svc = setup_store(tmp_path)
    seed_common_data(store)
    order_id = svc.create_draft_order("c1", "cu1")
    svc.add_item_to_draft(order_id, "c1", SaleItem(product_id="v1", qty=1, unit_selling_price=22))
    rows = svc.resolve_order_items("c1", order_id)
    assert len(rows) == 1
    assert rows.iloc[0]["parent_product_name"] == "Phone Case"
    assert rows.iloc[0]["variant_name"] == "Color:Red"
    assert "Phone Case" in rows.iloc[0]["product_display_name"]


def test_pricing_validation_blocks_below_minimum(tmp_path: Path):
    store, svc = setup_store(tmp_path)
    seed_common_data(store)
    order_id = svc.create_draft_order("c1", "cu1")
    try:
        svc.add_item_to_draft(
            order_id, "c1", SaleItem(product_id="p1", qty=1, unit_selling_price=10)
        )
        assert False, "Expected ValueError"
    except ValueError as exc:
        assert "below minimum" in str(exc)
