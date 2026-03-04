from pathlib import Path

from easy_ecom.data.store.csv_store import CsvStore
from easy_ecom.data.store.schema import TABLE_SCHEMAS
from easy_ecom.data.repos.csv.inventory_repo import InventoryTxnRepo
from easy_ecom.data.repos.csv.sequences_repo import SequencesRepo
from easy_ecom.domain.services.inventory_service import InventoryService, SequenceService


def setup_store(tmp_path: Path) -> CsvStore:
    store = CsvStore(tmp_path)
    for t, c in TABLE_SCHEMAS.items():
        store.ensure_table(t, c)
    return store


def test_fifo_allocation(tmp_path: Path):
    store = setup_store(tmp_path)
    svc = InventoryService(InventoryTxnRepo(store), SequenceService(SequencesRepo(store)))
    svc.add_stock("c1", "p1", 10, 5, "sup", "")
    svc.add_stock("c1", "p1", 5, 8, "sup", "")
    alloc = svc.allocate_fifo("c1", "p1", 12)
    assert alloc[0]["qty"] == 10
    assert alloc[1]["qty"] == 2
