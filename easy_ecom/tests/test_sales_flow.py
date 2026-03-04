from pathlib import Path

from easy_ecom.data.store.csv_store import CsvStore
from easy_ecom.data.store.schema import TABLE_SCHEMAS
from easy_ecom.data.repos.csv.finance_repo import LedgerRepo
from easy_ecom.data.repos.csv.inventory_repo import InventoryTxnRepo
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
    inv.add_stock("c1", "Phone Case", 10, 5, "sup", "")
    fin = FinanceService(LedgerRepo(store), InventoryTxnRepo(store))
    svc = SalesService(SalesOrdersRepo(store), SalesOrderItemsRepo(store), InvoicesRepo(store), ShipmentsRepo(store), PaymentsRepo(store), inv, seq, fin)
    result = svc.confirm_sale(SaleConfirm(client_id="c1", customer_id="cust1", items=[SaleItem(product_id="Phone Case", qty=2, unit_selling_price=20)]), {"full_name": "X", "phone": "1", "address_line1": "Addr"})
    assert result["invoice_no"].startswith("INV-")
    assert not LedgerRepo(store).all().empty
    assert inv.available_qty("c1", "Phone Case") == 8
