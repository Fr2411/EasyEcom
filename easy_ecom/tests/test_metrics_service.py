from pathlib import Path

import pandas as pd

from easy_ecom.data.repos.csv.finance_repo import LedgerRepo
from easy_ecom.data.repos.csv.inventory_repo import InventoryTxnRepo
from easy_ecom.data.repos.csv.product_variants_repo import ProductVariantsRepo
from easy_ecom.data.repos.csv.products_repo import ProductsRepo
from easy_ecom.data.repos.csv.sales_repo import (
    InvoicesRepo,
    PaymentsRepo,
    SalesOrderItemsRepo,
    SalesOrdersRepo,
)
from easy_ecom.domain.services.metrics_service import DateRange, MetricsService
from easy_ecom.tests.support.sqlite_runtime import build_sqlite_runtime


def setup_store(tmp_path: Path):
    return build_sqlite_runtime(tmp_path, "metrics.db").store


def build_svc(store) -> MetricsService:
    return MetricsService(
        InventoryTxnRepo(store),
        LedgerRepo(store),
        SalesOrdersRepo(store),
        InvoicesRepo(store),
        PaymentsRepo(store),
        SalesOrderItemsRepo(store),
        ProductsRepo(store),
        ProductVariantsRepo(store),
    )


def test_profit_includes_cogs(tmp_path: Path):
    store = setup_store(tmp_path)
    now = pd.Timestamp.utcnow().strftime("%Y-%m-%dT10:00:00Z")
    SalesOrdersRepo(store).append(
        {
            "order_id": "o1",
            "client_id": "c1",
            "timestamp": now,
            "customer_id": "cu",
            "status": "confirmed",
            "subtotal": "1250",
            "discount": "0",
            "tax": "0",
            "grand_total": "1250",
            "delivery_cost": "0",
            "delivery_provider": "",
            "note": "",
        }
    )
    InventoryTxnRepo(store).append(
        {
            "txn_id": "1",
            "client_id": "c1",
            "timestamp": now,
            "user_id": "",
            "txn_type": "OUT",
            "product_id": "p1",
            "qty": "5",
            "unit_cost": "100",
            "total_cost": "500",
            "supplier_snapshot": "",
            "note": "",
            "source_type": "sale",
            "source_id": "o1",
            "lot_id": "L1",
        }
    )
    svc = build_svc(store)
    assert (
        svc.profit("c1", DateRange(svc.month_start(), pd.Timestamp.utcnow().tz_localize(None)))
        == 750.0
    )


def test_stock_value_uses_lot_costs(tmp_path: Path):
    store = setup_store(tmp_path)
    now = pd.Timestamp.utcnow().strftime("%Y-%m-%dT10:00:00Z")
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
    inv = InventoryTxnRepo(store)
    inv.append(
        {
            "txn_id": "1",
            "client_id": "c1",
            "timestamp": now,
            "user_id": "",
            "txn_type": "IN",
            "product_id": "p1_LOT-1",
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
    inv.append(
        {
            "txn_id": "2",
            "client_id": "c1",
            "timestamp": now,
            "user_id": "",
            "txn_type": "IN",
            "product_id": "p1_LOT-2",
            "qty": "5",
            "unit_cost": "8",
            "total_cost": "40",
            "supplier_snapshot": "",
            "note": "",
            "source_type": "purchase",
            "source_id": "",
            "lot_id": "LOT-2",
        }
    )
    d = build_svc(store).current_stock_value_by_product("c1")
    assert float(d.iloc[0]["stock_value"]) == 90.0


def test_product_aging_math(tmp_path: Path):
    store = setup_store(tmp_path)
    now = pd.Timestamp.utcnow().strftime("%Y-%m-%dT10:00:00Z")
    inv = InventoryTxnRepo(store)
    inv.append(
        {
            "txn_id": "1",
            "client_id": "c1",
            "timestamp": now,
            "user_id": "",
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
            "txn_id": "2",
            "client_id": "c1",
            "timestamp": now,
            "user_id": "",
            "txn_type": "OUT",
            "product_id": "p1",
            "qty": "4",
            "unit_cost": "5",
            "total_cost": "20",
            "supplier_snapshot": "",
            "note": "",
            "source_type": "sale",
            "source_id": "",
            "lot_id": "L1",
        }
    )
    d = build_svc(store).product_aging("c1")
    assert round(float(d.iloc[0]["sold_pct"]), 2) == 40.0


def test_margin_math_guard_zero_revenue(tmp_path: Path):
    store = setup_store(tmp_path)
    svc = build_svc(store)
    d = svc.margin_by_product("c1")
    assert d.empty


def test_sell_speed_last_30_days(tmp_path: Path):
    store = setup_store(tmp_path)
    ts = (pd.Timestamp.utcnow() - pd.Timedelta(days=10)).strftime("%Y-%m-%dT10:00:00Z")
    InventoryTxnRepo(store).append(
        {
            "txn_id": "1",
            "client_id": "c1",
            "timestamp": ts,
            "user_id": "",
            "txn_type": "OUT",
            "product_id": "p1",
            "qty": "30",
            "unit_cost": "5",
            "total_cost": "150",
            "supplier_snapshot": "",
            "note": "",
            "source_type": "sale",
            "source_id": "",
            "lot_id": "L1",
        }
    )
    d = build_svc(store).sell_speed_by_product("c1", days=30)
    assert round(float(d.iloc[0]["sell_speed_units_per_day"]), 2) == 1.0


def test_lot_profit_recovery_allocation_consistency(tmp_path: Path):
    store = setup_store(tmp_path)
    now = pd.Timestamp.utcnow().strftime("%Y-%m-%dT10:00:00Z")
    inv = InventoryTxnRepo(store)
    inv.append(
        {
            "txn_id": "in1",
            "client_id": "c1",
            "timestamp": now,
            "user_id": "",
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
            "txn_id": "out1",
            "client_id": "c1",
            "timestamp": now,
            "user_id": "",
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
    SalesOrderItemsRepo(store).append(
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
    d = build_svc(store).lot_profit_recovery("c1")
    assert float(d.iloc[0]["recovered_revenue"]) == 100.0


def test_client_scoping_no_cross_tenant_leak(tmp_path: Path):
    store = setup_store(tmp_path)
    now = pd.Timestamp.utcnow().strftime("%Y-%m-%dT10:00:00Z")
    o = SalesOrdersRepo(store)
    o.append(
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
    o.append(
        {
            "order_id": "o2",
            "client_id": "c2",
            "timestamp": now,
            "customer_id": "cu",
            "status": "confirmed",
            "subtotal": "999",
            "discount": "0",
            "tax": "0",
            "grand_total": "999",
            "delivery_cost": "0",
            "delivery_provider": "",
            "note": "",
        }
    )
    assert build_svc(store).revenue("c1") == 100.0


def test_margin_includes_cogs_same_product_id(tmp_path: Path):
    store = setup_store(tmp_path)
    now = pd.Timestamp.utcnow().strftime("%Y-%m-%dT10:00:00Z")
    ProductsRepo(store).append(
        {
            "product_id": "11111111-1111-1111-1111-111111111111",
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
            "note": "",
        }
    )
    SalesOrderItemsRepo(store).append(
        {
            "order_item_id": "i1",
            "order_id": "o1",
            "product_id": "11111111-1111-1111-1111-111111111111",
            "prd_description_snapshot": "",
            "qty": "2",
            "unit_selling_price": "50",
            "total_selling_price": "100",
        }
    )
    InventoryTxnRepo(store).append(
        {
            "txn_id": "out1",
            "client_id": "c1",
            "timestamp": now,
            "user_id": "",
            "txn_type": "OUT",
            "product_id": "11111111-1111-1111-1111-111111111111",
            "qty": "2",
            "unit_cost": "30",
            "total_cost": "60",
            "supplier_snapshot": "",
            "note": "",
            "source_type": "sale",
            "source_id": "o1",
            "lot_id": "L1",
        }
    )

    d = build_svc(store).margin_by_product("c1")
    assert float(d.iloc[0]["margin_pct"]) == 40.0


def test_sold_qty_mtd_calculation(tmp_path: Path):
    store = setup_store(tmp_path)
    now = pd.Timestamp.utcnow().strftime("%Y-%m-%dT10:00:00Z")
    SalesOrdersRepo(store).append(
        {
            "order_id": "o1",
            "client_id": "c1",
            "timestamp": now,
            "customer_id": "cu",
            "status": "confirmed",
            "subtotal": "60",
            "discount": "0",
            "tax": "0",
            "grand_total": "60",
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
            "unit_selling_price": "20",
            "total_selling_price": "60",
        }
    )
    svc = build_svc(store)
    assert (
        svc.sold_qty("c1", DateRange(svc.month_start(), pd.Timestamp.utcnow().tz_localize(None)))
        == 3.0
    )


def test_orders_mtd_calculation(tmp_path: Path):
    store = setup_store(tmp_path)
    now = pd.Timestamp.utcnow().strftime("%Y-%m-%dT10:00:00Z")
    SalesOrdersRepo(store).append(
        {
            "order_id": "o1",
            "client_id": "c1",
            "timestamp": now,
            "customer_id": "cu",
            "status": "confirmed",
            "subtotal": "60",
            "discount": "0",
            "tax": "0",
            "grand_total": "60",
            "delivery_cost": "0",
            "delivery_provider": "",
            "note": "",
        }
    )
    SalesOrdersRepo(store).append(
        {
            "order_id": "o2",
            "client_id": "c1",
            "timestamp": now,
            "customer_id": "cu",
            "status": "draft",
            "subtotal": "0",
            "discount": "0",
            "tax": "0",
            "grand_total": "0",
            "delivery_cost": "0",
            "delivery_provider": "",
            "note": "",
        }
    )
    svc = build_svc(store)
    assert (
        svc.orders_count(
            "c1", DateRange(svc.month_start(), pd.Timestamp.utcnow().tz_localize(None))
        )
        == 1.0
    )


def test_product_aging_qty_and_pct(tmp_path: Path):
    store = setup_store(tmp_path)
    now = pd.Timestamp.utcnow().strftime("%Y-%m-%dT10:00:00Z")
    inv = InventoryTxnRepo(store)
    inv.append(
        {
            "txn_id": "1",
            "client_id": "c1",
            "timestamp": now,
            "user_id": "",
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
            "txn_id": "2",
            "client_id": "c1",
            "timestamp": now,
            "user_id": "",
            "txn_type": "OUT",
            "product_id": "p1",
            "qty": "4",
            "unit_cost": "5",
            "total_cost": "20",
            "supplier_snapshot": "",
            "note": "",
            "source_type": "sale",
            "source_id": "",
            "lot_id": "L1",
        }
    )
    d = build_svc(store).product_aging("c1")
    assert float(d.iloc[0]["sold_qty"]) == 4.0
    assert float(d.iloc[0]["current_qty"]) == 6.0
    assert round(float(d.iloc[0]["remaining_pct"]), 2) == 60.0


def test_margin_rolls_variant_sales_to_parent_product(tmp_path: Path):
    store = setup_store(tmp_path)
    now = pd.Timestamp.utcnow().strftime("%Y-%m-%dT10:00:00Z")
    ProductsRepo(store).append(
        {
            "product_id": "p1",
            "client_id": "c1",
            "supplier": "",
            "product_name": "Tee",
            "category": "",
            "prd_description": "",
            "prd_features_json": "{}",
            "created_at": now,
            "is_active": "true",
        }
    )
    ProductVariantsRepo(store).append(
        {
            "variant_id": "v1",
            "client_id": "c1",
            "parent_product_id": "p1",
            "variant_name": "Size:L",
            "size": "L",
            "color": "",
            "other": "",
            "sku_code": "",
            "default_selling_price": "100",
            "max_discount_pct": "10",
            "is_active": "true",
            "created_at": now,
        }
    )
    SalesOrdersRepo(store).append(
        {
            "order_id": "o1",
            "client_id": "c1",
            "timestamp": now,
            "customer_id": "cu",
            "status": "confirmed",
            "subtotal": "120",
            "discount": "0",
            "tax": "0",
            "grand_total": "120",
            "delivery_cost": "0",
            "delivery_provider": "",
            "note": "",
        }
    )
    SalesOrderItemsRepo(store).append(
        {
            "order_item_id": "i1",
            "order_id": "o1",
            "product_id": "v1",
            "prd_description_snapshot": "",
            "qty": "2",
            "unit_selling_price": "60",
            "total_selling_price": "120",
        }
    )
    InventoryTxnRepo(store).append(
        {
            "txn_id": "out1",
            "client_id": "c1",
            "timestamp": now,
            "user_id": "",
            "txn_type": "OUT",
            "product_id": "v1",
            "qty": "2",
            "unit_cost": "30",
            "total_cost": "60",
            "supplier_snapshot": "",
            "note": "",
            "source_type": "sale",
            "source_id": "o1",
            "lot_id": "L1",
        }
    )

    d = build_svc(store).margin_by_product("c1")
    assert float(d.iloc[0]["revenue"]) == 120.0
    assert float(d.iloc[0]["cogs"]) == 60.0
    assert float(d.iloc[0]["margin_pct"]) == 50.0
    assert d.iloc[0]["product_id"] == "p1"


def test_integrity_warnings_do_not_flag_valid_variant_identity_as_unknown(tmp_path: Path):
    store = setup_store(tmp_path)
    now = pd.Timestamp.utcnow().strftime("%Y-%m-%dT10:00:00Z")
    ProductsRepo(store).append(
        {
            "product_id": "p1",
            "client_id": "c1",
            "supplier": "",
            "product_name": "Tee",
            "category": "",
            "prd_description": "",
            "prd_features_json": "{}",
            "created_at": now,
            "is_active": "true",
        }
    )
    ProductVariantsRepo(store).append(
        {
            "variant_id": "v1",
            "client_id": "c1",
            "parent_product_id": "p1",
            "variant_name": "Size:L",
            "size": "L",
            "color": "",
            "other": "",
            "sku_code": "",
            "default_selling_price": "100",
            "max_discount_pct": "10",
            "is_active": "true",
            "created_at": now,
        }
    )
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
    SalesOrderItemsRepo(store).append(
        {
            "order_item_id": "i1",
            "order_id": "o1",
            "product_id": "v1",
            "prd_description_snapshot": "",
            "qty": "1",
            "unit_selling_price": "100",
            "total_selling_price": "100",
        }
    )

    warnings = build_svc(store).integrity_warnings("c1")
    assert not any("unknown product_id" in w.lower() for w in warnings)
    assert any("valid variant identities" in w.lower() for w in warnings)


def test_lot_profit_recovery_aligns_variant_sales_to_parent_identity(tmp_path: Path):
    store = setup_store(tmp_path)
    now = pd.Timestamp.utcnow().strftime("%Y-%m-%dT10:00:00Z")
    ProductsRepo(store).append(
        {
            "product_id": "p1",
            "client_id": "c1",
            "supplier": "",
            "product_name": "Tee",
            "category": "",
            "prd_description": "",
            "prd_features_json": "{}",
            "created_at": now,
            "is_active": "true",
        }
    )
    ProductVariantsRepo(store).append(
        {
            "variant_id": "v1",
            "client_id": "c1",
            "parent_product_id": "p1",
            "variant_name": "Size:L",
            "size": "L",
            "color": "",
            "other": "",
            "sku_code": "",
            "default_selling_price": "100",
            "max_discount_pct": "10",
            "is_active": "true",
            "created_at": now,
        }
    )
    InventoryTxnRepo(store).append(
        {
            "txn_id": "in1",
            "client_id": "c1",
            "timestamp": now,
            "user_id": "",
            "txn_type": "IN",
            "product_id": "v1",
            "qty": "2",
            "unit_cost": "30",
            "total_cost": "60",
            "supplier_snapshot": "",
            "note": "",
            "source_type": "purchase",
            "source_id": "",
            "lot_id": "L1",
        }
    )
    InventoryTxnRepo(store).append(
        {
            "txn_id": "out1",
            "client_id": "c1",
            "timestamp": now,
            "user_id": "",
            "txn_type": "OUT",
            "product_id": "v1",
            "qty": "2",
            "unit_cost": "30",
            "total_cost": "60",
            "supplier_snapshot": "",
            "note": "",
            "source_type": "sale",
            "source_id": "o1",
            "lot_id": "L1",
        }
    )
    SalesOrdersRepo(store).append(
        {
            "order_id": "o1",
            "client_id": "c1",
            "timestamp": now,
            "customer_id": "cu",
            "status": "confirmed",
            "subtotal": "120",
            "discount": "0",
            "tax": "0",
            "grand_total": "120",
            "delivery_cost": "0",
            "delivery_provider": "",
            "note": "",
        }
    )
    SalesOrderItemsRepo(store).append(
        {
            "order_item_id": "i1",
            "order_id": "o1",
            "product_id": "v1",
            "prd_description_snapshot": "",
            "qty": "2",
            "unit_selling_price": "60",
            "total_selling_price": "120",
        }
    )

    d = build_svc(store).lot_profit_recovery("c1")
    assert float(d.iloc[0]["recovered_revenue"]) == 120.0
    assert d.iloc[0]["product_id"] == "p1"
