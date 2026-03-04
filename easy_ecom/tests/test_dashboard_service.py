from pathlib import Path

import pandas as pd

from easy_ecom.data.repos.csv.clients_repo import ClientsRepo
from easy_ecom.data.repos.csv.finance_repo import LedgerRepo
from easy_ecom.data.repos.csv.inventory_repo import InventoryTxnRepo
from easy_ecom.data.repos.csv.products_repo import ProductsRepo
from easy_ecom.data.repos.csv.sales_repo import InvoicesRepo, SalesOrderItemsRepo, SalesOrdersRepo
from easy_ecom.data.store.csv_store import CsvStore
from easy_ecom.data.store.schema import TABLE_SCHEMAS
from easy_ecom.domain.services.dashboard_service import DashboardService


def setup_store(tmp_path: Path) -> CsvStore:
    store = CsvStore(tmp_path)
    for table_name, columns in TABLE_SCHEMAS.items():
        store.ensure_table(table_name, columns)
    return store


def build_service(store: CsvStore) -> DashboardService:
    return DashboardService(
        InventoryTxnRepo(store),
        LedgerRepo(store),
        SalesOrdersRepo(store),
        InvoicesRepo(store),
        SalesOrderItemsRepo(store),
        ProductsRepo(store),
        ClientsRepo(store),
    )


def test_dashboard_kpis_and_charts_data(tmp_path: Path):
    store = setup_store(tmp_path)
    clients = ClientsRepo(store)
    products = ProductsRepo(store)
    inv = InventoryTxnRepo(store)
    ledger = LedgerRepo(store)
    orders = SalesOrdersRepo(store)
    items = SalesOrderItemsRepo(store)
    invoices = InvoicesRepo(store)

    now = pd.Timestamp.utcnow().strftime("%Y-%m-%dT10:00:00")
    clients.append(
        {
            "client_id": "c1",
            "business_name": "Alpha",
            "owner_name": "O",
            "phone": "",
            "email": "",
            "address": "",
            "website_url": "",
            "facebook_url": "",
            "instagram_url": "",
            "whatsapp_number": "",
            "created_at": now,
            "status": "active",
            "notes": "",
        }
    )
    products.append(
        {
            "product_id": "p1",
            "client_id": "c1",
            "supplier": "sup",
            "product_name": "Product 1",
            "category": "cat",
            "prd_description": "",
            "prd_features_json": "{}",
            "created_at": now,
            "is_active": "True",
        }
    )

    inv.append(
        {
            "txn_id": "t1",
            "client_id": "c1",
            "timestamp": now,
            "txn_type": "IN",
            "product_id": "p1",
            "qty": "10",
            "unit_cost": "5",
            "total_cost": "50",
            "supplier_snapshot": "",
            "note": "",
            "source_type": "purchase",
            "source_id": "",
            "lot_id": "L1",
        }
    )
    inv.append(
        {
            "txn_id": "t2",
            "client_id": "c1",
            "timestamp": now,
            "txn_type": "OUT",
            "product_id": "p1",
            "qty": "4",
            "unit_cost": "5",
            "total_cost": "20",
            "supplier_snapshot": "",
            "note": "",
            "source_type": "sale",
            "source_id": "o1",
            "lot_id": "L1",
        }
    )

    ledger.append(
        {
            "entry_id": "e1",
            "client_id": "c1",
            "timestamp": now,
            "entry_type": "earning",
            "category": "sales",
            "amount": "100",
            "source_type": "sale",
            "source_id": "o1",
            "note": "",
        }
    )
    ledger.append(
        {
            "entry_id": "e2",
            "client_id": "c1",
            "timestamp": now,
            "entry_type": "expense",
            "category": "ops",
            "amount": "30",
            "source_type": "manual",
            "source_id": "x",
            "note": "",
        }
    )

    orders.append(
        {
            "order_id": "o1",
            "client_id": "c1",
            "timestamp": now,
            "customer_id": "cu1",
            "status": "confirmed",
            "subtotal": "100",
            "discount": "0",
            "tax": "0",
            "grand_total": "100",
            "note": "",
        }
    )
    items.append(
        {
            "order_item_id": "i1",
            "order_id": "o1",
            "product_id": "p1",
            "prd_description_snapshot": "",
            "qty": "4",
            "unit_selling_price": "25",
            "total_selling_price": "100",
        }
    )
    invoices.append(
        {
            "invoice_id": "in1",
            "client_id": "c1",
            "invoice_no": "INV-1",
            "order_id": "o1",
            "customer_id": "cu1",
            "timestamp": now,
            "amount_due": "40",
            "status": "unpaid",
        }
    )

    svc = build_service(store)
    kpis = svc.kpis("c1")

    assert kpis["Current Stock Value"] == 30.0
    assert kpis["Revenue MTD"] == 100.0
    assert kpis["Expenses MTD"] == 30.0
    assert kpis["Profit MTD"] == 70.0
    assert kpis["Orders MTD"] == 1.0
    assert kpis["AOV MTD"] == 100.0
    assert kpis["Outstanding Invoices"] == 40.0

    assert not svc.revenue_trend(
        "c1", "D", pd.Timestamp.utcnow() - pd.Timedelta(days=2), pd.Timestamp.utcnow()
    ).empty
    assert not svc.stock_value_by_product("c1").empty
    assert not svc.product_aging("c1").empty
    assert not svc.margin_sell_speed("c1").empty
    assert not svc.income_expense_trend(
        "c1", "D", pd.Timestamp.utcnow() - pd.Timedelta(days=2), pd.Timestamp.utcnow()
    ).empty
    assert not svc.lot_profitability("c1").empty
