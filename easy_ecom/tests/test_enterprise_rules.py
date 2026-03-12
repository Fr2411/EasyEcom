from pathlib import Path

import pytest

from easy_ecom.data.repos.csv.finance_repo import LedgerRepo
from easy_ecom.data.repos.csv.inventory_repo import InventoryTxnRepo
from easy_ecom.data.repos.csv.clients_repo import ClientsRepo
from easy_ecom.data.repos.csv.products_repo import ProductsRepo
from easy_ecom.data.repos.csv.sales_repo import InvoicesRepo, PaymentsRepo, RefundsRepo, ReturnItemsRepo, ReturnsRepo, SalesOrderItemsRepo, SalesOrdersRepo, ShipmentsRepo
from easy_ecom.data.repos.csv.sequences_repo import SequencesRepo
from easy_ecom.data.store.csv_store import CsvStore
from easy_ecom.data.store.schema import TABLE_SCHEMAS
from easy_ecom.domain.models.client import ClientCreate
from easy_ecom.domain.models.sales import ReturnItem, ReturnRequestCreate, SaleConfirm, SaleItem
from easy_ecom.domain.services.client_service import ClientService
from easy_ecom.domain.services.finance_service import FinanceService
from easy_ecom.domain.services.inventory_service import InventoryService, SequenceService
from easy_ecom.domain.services.returns_service import ReturnsService
from easy_ecom.domain.services.sales_service import SalesService


def setup_store(tmp_path: Path) -> CsvStore:
    store = CsvStore(tmp_path)
    for t, c in TABLE_SCHEMAS.items():
        store.ensure_table(t, c)
    return store


def test_min_price_enforcement(tmp_path: Path):
    store = setup_store(tmp_path)
    seq = SequenceService(SequencesRepo(store))
    inv = InventoryService(InventoryTxnRepo(store), seq)
    fin = FinanceService(LedgerRepo(store), InventoryTxnRepo(store))
    products_repo = ProductsRepo(store)
    products_repo.append({"product_id": "p1", "client_id": "c1", "supplier": "sup", "product_name": "Phone Case", "category": "General", "prd_description": "", "prd_features_json": "{}", "default_selling_price": "100", "max_discount_pct": "10", "created_at": "", "is_active": "true"})
    inv.add_stock("c1", "p1", "p1", "Phone Case", 10, 25, "sup", "")
    svc = SalesService(SalesOrdersRepo(store), SalesOrderItemsRepo(store), InvoicesRepo(store), ShipmentsRepo(store), PaymentsRepo(store), inv, seq, fin, products_repo)

    with pytest.raises(ValueError):
        svc.confirm_sale(SaleConfirm(client_id="c1", customer_id="cust1", items=[SaleItem(product_id="p1", qty=1, unit_selling_price=85)]), {"full_name": "X"})


def test_return_approval_permission_and_refund_ledger(tmp_path: Path):
    store = setup_store(tmp_path)
    seq = SequenceService(SequencesRepo(store))
    inv = InventoryService(InventoryTxnRepo(store), seq)
    fin = FinanceService(LedgerRepo(store), InventoryTxnRepo(store))
    svc = ReturnsService(ReturnsRepo(store), ReturnItemsRepo(store), RefundsRepo(store), fin, inv, SalesOrdersRepo(store))
    return_id = svc.create_request(ReturnRequestCreate(client_id="c1", invoice_id="inv1", order_id="ord1", customer_id="cust1", requested_by_user_id="u_emp", reason="Damaged", restock=False, items=[ReturnItem(product_id="Phone Case", qty=1, unit_selling_price=100)]))

    with pytest.raises(PermissionError):
        svc.approve_request("c1", return_id, "u_emp", ["CLIENT_EMPLOYEE"], True)

    status = svc.approve_request("c1", return_id, "u_mgr", ["CLIENT_MANAGER"], True)
    assert status == "APPROVED"
    svc.issue_refund(return_id, 100, "manual", user_ctx={"client_id": "c1", "user_id": "u_mgr"})
    refunds = RefundsRepo(store).all()
    assert len(refunds) == 1
    assert float(refunds.iloc[0]["amount"]) == 100

    ledger = LedgerRepo(store).all()
    refund_entries = ledger[(ledger["entry_type"] == "expense") & (ledger["category"] == "Refunds")]
    assert len(refund_entries) == 1
    assert float(refund_entries.iloc[0]["amount"]) == 100


def test_currency_fields_persist(tmp_path: Path):
    store = setup_store(tmp_path)
    svc = ClientService(ClientsRepo(store))
    client_id = svc.create(ClientCreate(business_name="B", owner_name="O", phone="", email="a@b.com", address="", currency_code="aed", currency_symbol="د.إ"))
    clients = svc.list_clients()
    row = clients[clients["client_id"] == client_id].iloc[0]
    assert row["currency_code"] == "AED"
    assert row["currency_symbol"] == "د.إ"
