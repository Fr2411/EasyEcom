from pathlib import Path

from easy_ecom.data.store.csv_store import CsvStore
from easy_ecom.data.store.schema import TABLE_SCHEMAS
from easy_ecom.data.repos.csv.finance_repo import LedgerRepo
from easy_ecom.data.repos.csv.inventory_repo import InventoryTxnRepo
from easy_ecom.data.repos.csv.sequences_repo import SequencesRepo
from easy_ecom.domain.services.finance_service import FinanceService
from easy_ecom.domain.services.inventory_service import InventoryService, SequenceService


def setup_store(tmp_path: Path) -> CsvStore:
    store = CsvStore(tmp_path)
    for t, c in TABLE_SCHEMAS.items():
        store.ensure_table(t, c)
    return store


def test_profit_mtd(tmp_path: Path):
    store = setup_store(tmp_path)
    inv_svc = InventoryService(InventoryTxnRepo(store), SequenceService(SequencesRepo(store)))
    inv_svc.add_stock("c1", "p1", 10, 5, "s", "")
    inv_svc.deduct_stock("c1", "p1", 2, "sale", "o1")
    fin = FinanceService(LedgerRepo(store), InventoryTxnRepo(store))
    fin.add_entry("c1", "earning", "Sales", 100, "sale", "i1")
    fin.add_entry("c1", "expense", "Ops", 20, "manual", "e1")
    assert fin.profit_mtd("c1") == 70
