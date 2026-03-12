from pathlib import Path

from easy_ecom.data.repos.csv.audit_repo import AuditRepo
from easy_ecom.data.repos.csv.customers_repo import CustomersRepo
from easy_ecom.data.store.csv_store import CsvStore
from easy_ecom.data.store.schema import TABLE_SCHEMAS
from easy_ecom.data.repos.csv.finance_repo import LedgerRepo
from easy_ecom.data.repos.csv.inventory_repo import InventoryTxnRepo
from easy_ecom.data.repos.csv.products_repo import ProductsRepo
from easy_ecom.data.repos.csv.sales_repo import InvoicesRepo, PaymentsRepo, SalesOrderItemsRepo, SalesOrdersRepo, ShipmentsRepo
from easy_ecom.data.repos.csv.sequences_repo import SequencesRepo
from easy_ecom.domain.models.sales import SaleConfirm, SaleItem
from easy_ecom.domain.services.finance_service import FinanceService
from easy_ecom.domain.services.inventory_service import InventoryService, SequenceService
from easy_ecom.domain.services.sales_service import SalesService


def setup_store(tmp_path: Path) -> CsvStore:
    store = CsvStore(tmp_path)
    for t, c in TABLE_SCHEMAS.items():
        store.ensure_table(t, c)
    return store


def test_confirm_sale(tmp_path: Path):
    store = setup_store(tmp_path)
    seq = SequenceService(SequencesRepo(store))
    inv = InventoryService(InventoryTxnRepo(store), seq)
    inv.add_stock("c1", "p1", "p1", "Phone Case", 10, 5, "sup", "")
    ProductsRepo(store).append({"product_id": "p1", "client_id": "c1", "supplier": "sup", "product_name": "Phone Case", "category": "General", "prd_description": "", "prd_features_json": "{}", "default_selling_price": "20", "max_discount_pct": "10", "created_at": "", "is_active": "true"})
    fin = FinanceService(LedgerRepo(store), InventoryTxnRepo(store))
    svc = SalesService(SalesOrdersRepo(store), SalesOrderItemsRepo(store), InvoicesRepo(store), ShipmentsRepo(store), PaymentsRepo(store), inv, seq, fin, ProductsRepo(store))
    result = svc.confirm_sale(SaleConfirm(client_id="c1", customer_id="cust1", items=[SaleItem(product_id="p1", qty=2, unit_selling_price=20)]), {"full_name": "X", "phone": "1", "address_line1": "Addr"}, user_id="u-789")
    assert result["invoice_no"].startswith("INV-")
    assert not LedgerRepo(store).all().empty
    assert inv.available_qty("c1", "p1") == 8
    assert set(LedgerRepo(store).all()["user_id"]) == {"u-789"}
    assert set(InventoryTxnRepo(store).all().query("txn_type == 'OUT'")["user_id"]) == {"u-789"}


def test_customer_match_prefills(tmp_path: Path):
    store = setup_store(tmp_path)
    repo = CustomersRepo(store)
    repo.append({"customer_id": "cu1", "client_id": "c1", "created_at": "", "full_name": "Alice", "phone": "111", "email": "a@x.com", "whatsapp": "", "address_line1": "Old", "address_line2": "", "area": "", "city": "", "state": "", "postal_code": "", "country": "", "preferred_contact_channel": "", "marketing_opt_in": "false", "tags": "", "notes": "", "is_active": "true"})
    matches = repo.find_by_name("c1", "alice")
    assert len(matches) == 1
    assert matches.iloc[0]["phone"] == "111"


def test_customer_auto_create_on_confirm(tmp_path: Path):
    store = setup_store(tmp_path)
    seq = SequenceService(SequencesRepo(store))
    inv = InventoryService(InventoryTxnRepo(store), seq)
    fin = FinanceService(LedgerRepo(store), InventoryTxnRepo(store))
    svc = SalesService(SalesOrdersRepo(store), SalesOrderItemsRepo(store), InvoicesRepo(store), ShipmentsRepo(store), PaymentsRepo(store), inv, seq, fin, ProductsRepo(store), CustomersRepo(store), AuditRepo(store))

    customer_id = svc.resolve_customer_for_sale("c1", {"full_name": "New Customer", "phone": "999", "email": "n@x.com", "address_line1": "Addr"}, matched_customer_id="", user_id="u1")
    customers = CustomersRepo(store).all()
    assert len(customers) == 1
    assert customers.iloc[0]["customer_id"] == customer_id
    assert not AuditRepo(store).all().empty


def test_customer_auto_update_on_confirm_when_fields_changed(tmp_path: Path):
    store = setup_store(tmp_path)
    CustomersRepo(store).append({"customer_id": "cu1", "client_id": "c1", "created_at": "", "full_name": "Alice", "phone": "111", "email": "a@x.com", "whatsapp": "", "address_line1": "Old", "address_line2": "", "area": "", "city": "", "state": "", "postal_code": "", "country": "", "preferred_contact_channel": "", "marketing_opt_in": "false", "tags": "", "notes": "", "is_active": "true"})

    seq = SequenceService(SequencesRepo(store))
    inv = InventoryService(InventoryTxnRepo(store), seq)
    fin = FinanceService(LedgerRepo(store), InventoryTxnRepo(store))
    svc = SalesService(SalesOrdersRepo(store), SalesOrderItemsRepo(store), InvoicesRepo(store), ShipmentsRepo(store), PaymentsRepo(store), inv, seq, fin, ProductsRepo(store), CustomersRepo(store), AuditRepo(store))

    resolved = svc.resolve_customer_for_sale("c1", {"full_name": "Alice", "phone": "222", "email": "a@x.com", "address_line1": "New"}, matched_customer_id="cu1", user_id="u1")
    assert resolved == "cu1"
    updated = CustomersRepo(store).all().iloc[0]
    assert updated["phone"] == "222"
    assert updated["address_line1"] == "New"
