from pathlib import Path

from easy_ecom.data.repos.csv.finance_repo import LedgerRepo
from easy_ecom.data.repos.csv.inventory_repo import InventoryTxnRepo
from easy_ecom.data.repos.csv.products_repo import ProductsRepo
from easy_ecom.data.repos.csv.sales_repo import SalesOrderItemsRepo, SalesOrdersRepo
from easy_ecom.data.repos.csv.sequences_repo import SequencesRepo
from easy_ecom.data.store.csv_store import CsvStore
from easy_ecom.data.store.schema import TABLE_SCHEMAS
from easy_ecom.domain.services.data_reconciliation_service import DataReconciliationService
from easy_ecom.domain.services.inventory_service import InventoryService, SequenceService
from easy_ecom.domain.services.metrics_service import MetricsService
from easy_ecom.data.repos.csv.sales_repo import InvoicesRepo, PaymentsRepo


def setup_store(tmp_path: Path) -> CsvStore:
    store = CsvStore(tmp_path)
    for t, c in TABLE_SCHEMAS.items():
        store.ensure_table(t, c)
    return store


def build_metrics(store: CsvStore) -> MetricsService:
    return MetricsService(
        InventoryTxnRepo(store),
        LedgerRepo(store),
        SalesOrdersRepo(store),
        InvoicesRepo(store),
        PaymentsRepo(store),
        SalesOrderItemsRepo(store),
        ProductsRepo(store),
    )


def test_inventory_legacy_product_mapping_is_visible_in_inventory_service(tmp_path: Path):
    store = setup_store(tmp_path)
    now = "2026-01-01T10:00:00Z"
    ProductsRepo(store).append(
        {
            "product_id": "p1",
            "client_id": "c1",
            "supplier": "",
            "product_name": "Headphone",
            "category": "",
            "prd_description": "",
            "prd_features_json": "{}",
            "created_at": now,
            "is_active": "true",
        }
    )
    InventoryTxnRepo(store).append(
        {
            "txn_id": "1",
            "client_id": "c1",
            "timestamp": now,
            "user_id": "",
            "txn_type": "IN",
            "product_id": "p1_LOT-1",
            "product_name": "",
            "qty": "10",
            "unit_cost": "5",
            "total_cost": "50",
            "supplier_snapshot": "",
            "note": "",
            "source_type": "purchase",
            "source_id": "",
            "lot_id": "LOT-1",
        }
    )

    svc = InventoryService(InventoryTxnRepo(store), SequenceService(SequencesRepo(store)))
    stock = svc.stock_by_lot("c1")
    assert stock.iloc[0]["product_id"] == "p1"


def test_dashboard_inventory_total_matches_inventory_service_total(tmp_path: Path):
    store = setup_store(tmp_path)
    now = "2026-01-01T10:00:00Z"
    ProductsRepo(store).append(
        {
            "product_id": "p1",
            "client_id": "c1",
            "supplier": "",
            "product_name": "Widget",
            "category": "",
            "prd_description": "",
            "prd_features_json": "{}",
            "created_at": now,
            "is_active": "true",
        }
    )
    inv = InventoryTxnRepo(store)
    inv.append(
        {
            "txn_id": "1",
            "client_id": "c1",
            "timestamp": now,
            "user_id": "",
            "txn_type": "IN",
            "product_id": "p1",
            "product_name": "Widget",
            "qty": "10",
            "unit_cost": "2",
            "total_cost": "20",
            "supplier_snapshot": "",
            "note": "",
            "source_type": "purchase",
            "source_id": "",
            "lot_id": "L1",
        }
    )
    inv.append(
        {
            "txn_id": "2",
            "client_id": "c1",
            "timestamp": now,
            "user_id": "",
            "txn_type": "OUT",
            "product_id": "p1",
            "product_name": "Widget",
            "qty": "3",
            "unit_cost": "2",
            "total_cost": "6",
            "supplier_snapshot": "",
            "note": "",
            "source_type": "sale",
            "source_id": "o1",
            "lot_id": "L1",
        }
    )

    inv_svc = InventoryService(InventoryTxnRepo(store), SequenceService(SequencesRepo(store)))
    metrics = build_metrics(store)
    assert float(inv_svc.stock_by_lot("c1")["qty"].sum()) == float(
        metrics.current_stock_qty_by_product("c1")["current_qty"].sum()
    )


def test_confirmed_sales_reconcile_with_metrics_revenue(tmp_path: Path):
    store = setup_store(tmp_path)
    now = "2026-01-01T10:00:00Z"
    SalesOrdersRepo(store).append(
        {
            "order_id": "o1",
            "client_id": "c1",
            "timestamp": now,
            "customer_id": "cu",
            "status": "confirmed",
            "subtotal": "150",
            "discount": "0",
            "tax": "0",
            "grand_total": "150",
            "delivery_cost": "0",
            "delivery_provider": "",
            "note": "",
        }
    )
    SalesOrderItemsRepo(store).append(
        {
            "order_item_id": "i1",
            "order_id": "o1",
            "product_id": "p1",
            "prd_description_snapshot": "",
            "qty": "3",
            "unit_selling_price": "50",
            "total_selling_price": "150",
        }
    )

    recon = DataReconciliationService(
        InventoryTxnRepo(store),
        ProductsRepo(store),
        SalesOrdersRepo(store),
        SalesOrderItemsRepo(store),
        LedgerRepo(store),
    )
    metrics = build_metrics(store)
    records = recon.confirmed_sales_with_reconciliation("c1")
    assert len(records) == 1
    assert bool(records.iloc[0]["has_items"]) is True
    assert metrics.revenue("c1") == 150.0


def test_orphan_ledger_and_unmapped_inventory_are_flagged(tmp_path: Path):
    store = setup_store(tmp_path)
    now = "2026-01-01T10:00:00Z"
    LedgerRepo(store).append(
        {
            "entry_id": "e1",
            "client_id": "c1",
            "timestamp": now,
            "user_id": "",
            "entry_type": "earning",
            "category": "sales",
            "amount": "99",
            "source_type": "sale",
            "source_id": "missing-order",
            "note": "",
        }
    )
    InventoryTxnRepo(store).append(
        {
            "txn_id": "t1",
            "client_id": "c1",
            "timestamp": now,
            "user_id": "",
            "txn_type": "IN",
            "product_id": "unknown-product",
            "product_name": "Old Name",
            "qty": "1",
            "unit_cost": "3",
            "total_cost": "3",
            "supplier_snapshot": "",
            "note": "",
            "source_type": "purchase",
            "source_id": "",
            "lot_id": "L1",
        }
    )

    recon = DataReconciliationService(
        InventoryTxnRepo(store),
        ProductsRepo(store),
        SalesOrdersRepo(store),
        SalesOrderItemsRepo(store),
        LedgerRepo(store),
    )
    issues = recon.integrity_issues("c1")
    issue_types = {i.issue_type for i in issues}
    assert "orphan_ledger_earning" in issue_types
    assert "inventory_unmapped_product" in issue_types


def test_reconciliation_preserves_client_scoping(tmp_path: Path):
    store = setup_store(tmp_path)
    now = "2026-01-01T10:00:00Z"
    SalesOrdersRepo(store).append(
        {
            "order_id": "o1",
            "client_id": "c1",
            "timestamp": now,
            "customer_id": "cu",
            "status": "confirmed",
            "subtotal": "100",
            "discount": "0",
            "tax": "0",
            "grand_total": "100",
            "delivery_cost": "0",
            "delivery_provider": "",
            "note": "",
        }
    )
    SalesOrdersRepo(store).append(
        {
            "order_id": "o2",
            "client_id": "c2",
            "timestamp": now,
            "customer_id": "cu",
            "status": "confirmed",
            "subtotal": "500",
            "discount": "0",
            "tax": "0",
            "grand_total": "500",
            "delivery_cost": "0",
            "delivery_provider": "",
            "note": "",
        }
    )
    recon = DataReconciliationService(
        InventoryTxnRepo(store),
        ProductsRepo(store),
        SalesOrdersRepo(store),
        SalesOrderItemsRepo(store),
        LedgerRepo(store),
    )
    c1 = recon.confirmed_sales_with_reconciliation("c1")
    assert list(c1["order_id"]) == ["o1"]
