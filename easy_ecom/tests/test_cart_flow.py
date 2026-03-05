from pathlib import Path

from easy_ecom.app.ui.documents import build_invoice_pdf
from easy_ecom.data.repos.csv.customers_repo import CustomersRepo
from easy_ecom.data.repos.csv.finance_repo import LedgerRepo
from easy_ecom.data.repos.csv.inventory_repo import InventoryTxnRepo
from easy_ecom.data.repos.csv.products_repo import ProductsRepo
from easy_ecom.data.repos.csv.sales_repo import InvoicesRepo, PaymentsRepo, SalesOrderItemsRepo, SalesOrdersRepo, ShipmentsRepo
from easy_ecom.data.repos.csv.sequences_repo import SequencesRepo
from easy_ecom.data.store.csv_store import CsvStore
from easy_ecom.data.store.schema import TABLE_SCHEMAS
from easy_ecom.domain.services.finance_service import FinanceService
from easy_ecom.domain.services.inventory_service import InventoryService, SequenceService
from easy_ecom.domain.services.sales_service import SalesService


def setup_store(tmp_path: Path) -> tuple[CsvStore, SalesService]:
    store = CsvStore(tmp_path)
    for t, c in TABLE_SCHEMAS.items():
        store.ensure_table(t, c)
    seq = SequenceService(SequencesRepo(store))
    inv = InventoryService(InventoryTxnRepo(store), seq)
    fin = FinanceService(LedgerRepo(store), InventoryTxnRepo(store))
    svc = SalesService(SalesOrdersRepo(store), SalesOrderItemsRepo(store), InvoicesRepo(store), ShipmentsRepo(store), PaymentsRepo(store), inv, seq, fin, ProductsRepo(store), CustomersRepo(store))
    return store, svc


def seed_common_data(store: CsvStore):
    ProductsRepo(store).append({"product_id": "p1", "client_id": "c1", "supplier": "sup", "product_name": "Phone Case", "category": "General", "prd_description": "", "prd_features_json": "{}", "default_selling_price": "20", "max_discount_pct": "10", "created_at": "", "is_active": "true"})
    ProductsRepo(store).append({"product_id": "p2", "client_id": "c1", "supplier": "sup", "product_name": "Charger", "category": "General", "prd_description": "", "prd_features_json": "{}", "default_selling_price": "40", "max_discount_pct": "20", "created_at": "", "is_active": "true"})
    CustomersRepo(store).append({"customer_id": "cu1", "client_id": "c1", "created_at": "", "full_name": "Alice", "phone": "111", "email": "a@x.com", "whatsapp": "", "address_line1": "A1", "address_line2": "", "area": "", "city": "Dubai", "state": "", "postal_code": "", "country": "", "preferred_contact_channel": "", "marketing_opt_in": "false", "tags": "", "notes": "", "is_active": "true"})
    CustomersRepo(store).append({"customer_id": "cu2", "client_id": "c1", "created_at": "", "full_name": "Bob", "phone": "222", "email": "b@x.com", "whatsapp": "", "address_line1": "B1", "address_line2": "", "area": "", "city": "Sharjah", "state": "", "postal_code": "", "country": "", "preferred_contact_channel": "", "marketing_opt_in": "false", "tags": "", "notes": "", "is_active": "true"})


def test_cart_tab_lists_draft_orders_grouped(tmp_path: Path):
    store, svc = setup_store(tmp_path)
    seed_common_data(store)
    SalesOrdersRepo(store).append({"order_id": "o1", "client_id": "c1", "timestamp": "2025-01-01T00:00:00Z", "customer_id": "cu1", "status": "draft", "subtotal": "0", "discount": "0", "tax": "0", "grand_total": "0", "note": ""})
    SalesOrdersRepo(store).append({"order_id": "o2", "client_id": "c1", "timestamp": "2025-01-02T00:00:00Z", "customer_id": "cu1", "status": "draft", "subtotal": "0", "discount": "0", "tax": "0", "grand_total": "0", "note": ""})
    SalesOrdersRepo(store).append({"order_id": "o3", "client_id": "c1", "timestamp": "2025-01-03T00:00:00Z", "customer_id": "cu2", "status": "draft", "subtotal": "0", "discount": "0", "tax": "0", "grand_total": "0", "note": ""})
    SalesOrderItemsRepo(store).append({"order_item_id": "i1", "order_id": "o1", "product_id": "p1", "prd_description_snapshot": "", "qty": "1", "unit_selling_price": "20", "total_selling_price": "20"})
    SalesOrderItemsRepo(store).append({"order_item_id": "i2", "order_id": "o2", "product_id": "p2", "prd_description_snapshot": "", "qty": "2", "unit_selling_price": "40", "total_selling_price": "80"})

    drafts = svc.list_draft_orders("c1")
    assert len(drafts) == 3
    grouped = drafts.groupby("customer_id").size().to_dict()
    assert grouped["cu1"] == 2
    assert grouped["cu2"] == 1


def test_confirm_from_cart_creates_invoice_and_shipment(tmp_path: Path):
    store, svc = setup_store(tmp_path)
    seed_common_data(store)
    seq = SequenceService(SequencesRepo(store))
    inv = InventoryService(InventoryTxnRepo(store), seq)
    inv.add_stock("c1", "p1", "Phone Case", 10, 5, "sup", "")

    SalesOrdersRepo(store).append({"order_id": "o1", "client_id": "c1", "timestamp": "2025-01-01T00:00:00Z", "customer_id": "cu1", "status": "draft", "subtotal": "0", "discount": "0", "tax": "0", "grand_total": "0", "note": ""})
    SalesOrderItemsRepo(store).append({"order_item_id": "i1", "order_id": "o1", "product_id": "p1", "prd_description_snapshot": "", "qty": "2", "unit_selling_price": "20", "total_selling_price": "40"})

    result = svc.confirm_order("o1", {"client_id": "c1", "user_id": "u1"})
    assert result["invoice_no"].startswith("INV-")
    assert result["shipment_no"].startswith("SHP-")
    assert SalesOrdersRepo(store).all().iloc[0]["status"] == "confirmed"
    assert len(InvoicesRepo(store).all()) == 1
    assert len(ShipmentsRepo(store).all()) == 1


def test_download_invoice_pdf_bytes_generated(tmp_path: Path):
    store, svc = setup_store(tmp_path)
    seed_common_data(store)
    pdf = build_invoice_pdf(
        {"business_name": "Biz", "phone": "123", "email": "x@y.com", "address": "Addr"},
        CustomersRepo(store).get("cu1") or {},
        {"order_id": "o1"},
        [{"product_id": "p1", "product_name": "Phone Case", "qty": "1", "unit_selling_price": "20"}],
        {"invoice_no": "INV-2025-00001"},
    )
    assert isinstance(pdf, bytes)
    assert len(pdf) > 100
    assert pdf.startswith(b"%PDF")


def test_confirm_prevents_double_confirm(tmp_path: Path):
    store, svc = setup_store(tmp_path)
    seed_common_data(store)
    seq = SequenceService(SequencesRepo(store))
    inv = InventoryService(InventoryTxnRepo(store), seq)
    inv.add_stock("c1", "p1", "Phone Case", 10, 5, "sup", "")

    SalesOrdersRepo(store).append({"order_id": "o1", "client_id": "c1", "timestamp": "2025-01-01T00:00:00Z", "customer_id": "cu1", "status": "draft", "subtotal": "0", "discount": "0", "tax": "0", "grand_total": "0", "note": ""})
    SalesOrderItemsRepo(store).append({"order_item_id": "i1", "order_id": "o1", "product_id": "p1", "prd_description_snapshot": "", "qty": "1", "unit_selling_price": "20", "total_selling_price": "20"})

    svc.confirm_order("o1", {"client_id": "c1", "user_id": "u1"})
    try:
        svc.confirm_order("o1", {"client_id": "c1", "user_id": "u1"})
        assert False, "Expected ValueError"
    except ValueError as exc:
        assert "already confirmed" in str(exc)


def test_cart_confirm_posts_delivery_expense(tmp_path: Path):
    store, svc = setup_store(tmp_path)
    seed_common_data(store)
    seq = SequenceService(SequencesRepo(store))
    inv = InventoryService(InventoryTxnRepo(store), seq)
    inv.add_stock("c1", "p1", "Phone Case", 10, 5, "sup", "")
    SalesOrdersRepo(store).append({"order_id": "o1", "client_id": "c1", "timestamp": "2025-01-01T00:00:00Z", "customer_id": "cu1", "status": "draft", "subtotal": "0", "discount": "0", "tax": "0", "grand_total": "0", "delivery_cost": "15", "delivery_provider": "DHL", "note": ""})
    SalesOrderItemsRepo(store).append({"order_item_id": "i1", "order_id": "o1", "product_id": "p1", "prd_description_snapshot": "", "qty": "1", "unit_selling_price": "20", "total_selling_price": "20"})
    svc.confirm_order("o1", {"client_id": "c1", "user_id": "u1"})
    ledger = LedgerRepo(store).all()
    delivery = ledger[(ledger["entry_type"] == "expense") & (ledger["category"] == "Delivery")]
    assert len(delivery) == 1
    assert float(delivery.iloc[0]["amount"]) == 15.0


def test_cart_confirm_creates_invoice_shipment_pdfs(tmp_path: Path):
    store, svc = setup_store(tmp_path)
    seed_common_data(store)
    seq = SequenceService(SequencesRepo(store))
    inv = InventoryService(InventoryTxnRepo(store), seq)
    inv.add_stock("c1", "p1", "Phone Case", 10, 5, "sup", "")
    SalesOrdersRepo(store).append({"order_id": "o1", "client_id": "c1", "timestamp": "2025-01-01T00:00:00Z", "customer_id": "cu1", "status": "draft", "subtotal": "0", "discount": "0", "tax": "0", "grand_total": "0", "delivery_cost": "0", "delivery_provider": "", "note": ""})
    SalesOrderItemsRepo(store).append({"order_item_id": "i1", "order_id": "o1", "product_id": "p1", "prd_description_snapshot": "", "qty": "1", "unit_selling_price": "20", "total_selling_price": "20"})
    result = svc.confirm_order("o1", {"client_id": "c1", "user_id": "u1"})
    assert result["invoice_no"].startswith("INV-") and result["shipment_no"].startswith("SHP-")


def test_cart_lists_draft_orders_by_customer(tmp_path: Path):
    store, svc = setup_store(tmp_path)
    seed_common_data(store)
    SalesOrdersRepo(store).append({"order_id": "o1", "client_id": "c1", "timestamp": "2025-01-01T00:00:00Z", "customer_id": "cu1", "status": "draft", "subtotal": "0", "discount": "0", "tax": "0", "grand_total": "0", "delivery_cost": "0", "delivery_provider": "", "note": ""})
    SalesOrdersRepo(store).append({"order_id": "o2", "client_id": "c1", "timestamp": "2025-01-02T00:00:00Z", "customer_id": "cu2", "status": "draft", "subtotal": "0", "discount": "0", "tax": "0", "grand_total": "0", "delivery_cost": "0", "delivery_provider": "", "note": ""})
    drafts = svc.list_draft_orders("c1")
    grouped = drafts.groupby("customer_id").size().to_dict()
    assert grouped == {"cu1": 1, "cu2": 1}
