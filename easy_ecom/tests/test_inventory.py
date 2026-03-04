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
    svc.add_stock("c1", "Phone Case", 10, 5, "sup", "")
    svc.add_stock("c1", "Phone Case", 5, 8, "sup", "")
    alloc = svc.allocate_fifo("c1", "Phone Case", 12)
    assert alloc[0]["qty"] == 10
    assert alloc[1]["qty"] == 2


def test_inventory_scoped_to_client(tmp_path: Path):
    store = setup_store(tmp_path)
    svc = InventoryService(InventoryTxnRepo(store), SequenceService(SequencesRepo(store)))
    svc.add_stock("c1", "Phone Case", 10, 5, "sup", "")
    svc.add_stock("c2", "Phone Case", 7, 6, "sup", "")

    c1_stock = svc.stock_by_lot("c1")
    assert c1_stock["qty"].sum() == 10
    assert set(c1_stock["product_name"]) == {"Phone Case"}


def test_product_id_is_name_plus_lot_id(tmp_path: Path):
    store = setup_store(tmp_path)
    svc = InventoryService(InventoryTxnRepo(store), SequenceService(SequencesRepo(store)))
    lot_id = svc.add_stock("c1", "Phone Case", 3, 2, "sup", "")

    stock = svc.stock_by_lot("c1")
    assert stock.iloc[0]["product_id"] == f"Phone_Case_{lot_id}"
