from pathlib import Path

import pytest

from easy_ecom.data.repos.csv.finance_repo import LedgerRepo
from easy_ecom.data.repos.csv.inventory_repo import InventoryTxnRepo
from easy_ecom.data.repos.csv.products_repo import ProductsRepo
from easy_ecom.data.repos.csv.sales_repo import InvoicesRepo, PaymentsRepo, RefundsRepo, ReturnItemsRepo, ReturnsRepo, SalesOrderItemsRepo, SalesOrdersRepo, ShipmentsRepo
from easy_ecom.data.repos.csv.sequences_repo import SequencesRepo
from easy_ecom.data.store.csv_store import CsvStore
from easy_ecom.data.store.schema import TABLE_SCHEMAS
from easy_ecom.domain.models.sales import ReturnItem, ReturnRequestCreate, SaleConfirm, SaleItem
from easy_ecom.domain.services.finance_service import FinanceService
from easy_ecom.domain.services.inventory_service import InventoryService, SequenceService
from easy_ecom.domain.services.returns_service import ReturnsService
from easy_ecom.domain.services.sales_service import SalesService


def setup_store(tmp_path: Path):
    store = CsvStore(tmp_path)
    for t, c in TABLE_SCHEMAS.items():
        store.ensure_table(t, c)
    seq = SequenceService(SequencesRepo(store))
    inv = InventoryService(InventoryTxnRepo(store), seq)
    fin = FinanceService(LedgerRepo(store), InventoryTxnRepo(store))
    svc = SalesService(SalesOrdersRepo(store), SalesOrderItemsRepo(store), InvoicesRepo(store), ShipmentsRepo(store), PaymentsRepo(store), inv, seq, fin, ProductsRepo(store))
    ret = ReturnsService(ReturnsRepo(store), ReturnItemsRepo(store), RefundsRepo(store), fin, inv, SalesOrdersRepo(store))
    return store, svc, ret, inv


def seed_product(store: CsvStore, inv: InventoryService):
    ProductsRepo(store).append({"product_id": "p1", "client_id": "c1", "supplier": "sup", "product_name": "Phone", "category": "General", "prd_description": "", "prd_features_json": "{}", "default_selling_price": "100", "max_discount_pct": "10", "created_at": "", "is_active": "true", "is_parent": "true", "sizes_csv": "", "colors_csv": "", "others_csv": "", "parent_product_id": ""})
    inv.add_stock("c1", "p1", "Phone", 10, 50, "sup", "")


def make_draft(svc: SalesService):
    oid = svc.create_draft_order("c1", "cu1")
    svc.add_item_to_draft(oid, "c1", SaleItem(product_id="p1", qty=2, unit_selling_price=100))
    return oid


def test_place_order_from_draft_locks_commercial_values(tmp_path: Path):
    store, svc, _, inv = setup_store(tmp_path)
    seed_product(store, inv)
    oid = make_draft(svc)
    svc.place_order_from_draft(oid, {"client_id": "c1", "user_id": "u1"})
    with pytest.raises(ValueError):
        svc.update_order_pricing(oid, "c1", 10, 1, 2, "X", "")


def test_payment_status_transitions_unpaid_partial_paid_paid(tmp_path: Path):
    store, svc, _, inv = setup_store(tmp_path)
    seed_product(store, inv)
    oid = make_draft(svc)
    svc.confirm_order(oid, {"client_id": "c1", "user_id": "u1"})
    assert svc.get_order(oid)["payment_status"] == "unpaid"
    svc.record_payment(oid, 50, "cash")
    assert svc.get_order(oid)["payment_status"] == "partially_paid"
    svc.record_payment(oid, 150, "cash")
    assert svc.get_order(oid)["payment_status"] == "paid"


def test_invoice_balance_updates_after_payments(tmp_path: Path):
    store, svc, _, inv = setup_store(tmp_path)
    seed_product(store, inv)
    oid = make_draft(svc)
    svc.confirm_order(oid, {"client_id": "c1", "user_id": "u1"})
    svc.record_payment(oid, 120, "bank")
    invoice = InvoicesRepo(store).all().iloc[0]
    assert float(invoice["amount_due"]) == 80.0


def test_fulfillment_status_progression(tmp_path: Path):
    store, svc, _, inv = setup_store(tmp_path)
    seed_product(store, inv)
    oid = make_draft(svc)
    svc.confirm_order(oid, {"client_id": "c1", "user_id": "u1"})
    svc.mark_ready_to_pack(oid, {"client_id": "c1", "user_id": "u1"})
    svc.mark_packed(oid, {"client_id": "c1", "user_id": "u1"})
    svc.create_shipment_for_order(oid, {"carrier": "DHL", "tracking_no": "T1"}, {"client_id": "c1", "user_id": "u1"})
    svc.mark_delivered(oid, {"client_id": "c1", "user_id": "u1"})
    assert svc.get_order(oid)["fulfillment_status"] == "delivered"


def test_shipment_not_auto_created_on_order_place(tmp_path: Path):
    store, svc, _, inv = setup_store(tmp_path)
    seed_product(store, inv)
    oid = make_draft(svc)
    svc.place_order_from_draft(oid, {"client_id": "c1", "user_id": "u1"})
    assert ShipmentsRepo(store).all().empty


def test_return_request_and_approval_flow(tmp_path: Path):
    store, svc, ret, inv = setup_store(tmp_path)
    seed_product(store, inv)
    oid = make_draft(svc)
    svc.confirm_order(oid, {"client_id": "c1", "user_id": "u1"})
    invoice = InvoicesRepo(store).all().iloc[0]
    rid = ret.request_return(oid, [{"product_id": "p1", "qty_requested": 1, "unit_selling_price": 100}], "damaged", {"client_id": "c1", "invoice_id": invoice["invoice_id"], "customer_id": "cu1", "user_id": "u2"})
    ret.approve_return(rid, {"client_id": "c1", "user_id": "mgr"})
    assert ReturnsRepo(store).all().iloc[0]["status"] == "approved"


def test_partial_refund_updates_financial_status(tmp_path: Path):
    store, svc, ret, inv = setup_store(tmp_path)
    seed_product(store, inv)
    oid = make_draft(svc)
    svc.confirm_order(oid, {"client_id": "c1", "user_id": "u1"})
    svc.record_payment(oid, 200, "cash")
    invoice = InvoicesRepo(store).all().iloc[0]
    rid = ret.request_return(oid, [{"product_id": "p1", "qty_requested": 1, "unit_selling_price": 100, "restock": True}], "damaged", {"client_id": "c1", "invoice_id": invoice["invoice_id"], "customer_id": "cu1", "user_id": "u2"})
    ret.approve_return(rid, {"client_id": "c1", "user_id": "mgr"})
    ret.issue_refund(rid, 40, "bank", restock_lines=False, user_ctx={"client_id": "c1", "user_id": "mgr"})
    assert SalesOrdersRepo(store).all().iloc[0]["return_status"] == "refund_completed"


def test_restock_on_refund_updates_inventory_when_enabled(tmp_path: Path):
    store, svc, ret, inv = setup_store(tmp_path)
    seed_product(store, inv)
    oid = make_draft(svc)
    svc.confirm_order(oid, {"client_id": "c1", "user_id": "u1"})
    before = inv.available_qty("c1", "p1")
    invoice = InvoicesRepo(store).all().iloc[0]
    rid = ret.request_return(oid, [{"product_id": "p1", "qty_requested": 1, "qty_received": 1, "unit_selling_price": 100, "restock": True}], "damaged", {"client_id": "c1", "invoice_id": invoice["invoice_id"], "customer_id": "cu1", "user_id": "u2"})
    ret.approve_return(rid, {"client_id": "c1", "user_id": "mgr"})
    ret.issue_refund(rid, 20, "cash", restock_lines=True, user_ctx={"client_id": "c1", "user_id": "mgr"})
    assert inv.available_qty("c1", "p1") >= before


def test_invalid_actions_blocked_by_state(tmp_path: Path):
    store, svc, _, inv = setup_store(tmp_path)
    seed_product(store, inv)
    oid = make_draft(svc)
    with pytest.raises(ValueError):
        svc.record_payment(oid, 10, "cash")


def test_legacy_confirm_sale_still_works_or_is_safely_wrapped(tmp_path: Path):
    store, svc, _, inv = setup_store(tmp_path)
    seed_product(store, inv)
    result = svc.confirm_sale(SaleConfirm(client_id="c1", customer_id="cu1", items=[SaleItem(product_id="p1", qty=1, unit_selling_price=100)]), {}, user_id="u1")
    assert result["order_id"]


def test_backward_compat_old_rows_without_new_status_columns(tmp_path: Path):
    store = CsvStore(tmp_path)
    store.ensure_table("sales_orders.csv", ["order_id", "client_id", "timestamp", "customer_id", "status", "subtotal", "discount", "tax", "grand_total", "delivery_cost", "delivery_provider", "note"])
    store.append("sales_orders.csv", {"order_id": "o1", "client_id": "c1", "timestamp": "", "customer_id": "cu1", "status": "confirmed", "subtotal": "10", "discount": "0", "tax": "0", "grand_total": "10", "delivery_cost": "0", "delivery_provider": "", "note": ""})
    for t, c in TABLE_SCHEMAS.items():
        if t != "sales_orders.csv":
            store.ensure_table(t, c)
    seq = SequenceService(SequencesRepo(store))
    svc = SalesService(SalesOrdersRepo(store), SalesOrderItemsRepo(store), InvoicesRepo(store), ShipmentsRepo(store), PaymentsRepo(store), InventoryService(InventoryTxnRepo(store), seq), seq, FinanceService(LedgerRepo(store), InventoryTxnRepo(store)), ProductsRepo(store))
    order = svc.get_order("o1")
    assert order["order_status"] == "confirmed"
