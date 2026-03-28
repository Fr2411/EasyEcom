from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select

from easy_ecom.api import dependencies as deps
from easy_ecom.api.main import create_app
from easy_ecom.core.ids import new_uuid
from easy_ecom.core.security import hash_password
from easy_ecom.data.store.postgres_models import (
    CategoryModel,
    ClientSettingsModel,
    CustomerModel,
    ExpenseModel,
    InventoryLedgerModel,
    LocationModel,
    PaymentModel,
    ProductModel,
    ProductVariantModel,
    PurchaseItemModel,
    PurchaseModel,
    SalesOrderItemModel,
    SalesOrderModel,
    SalesReturnItemModel,
    SalesReturnModel,
    SupplierModel,
)
from easy_ecom.tests.support.sqlite_runtime import build_sqlite_runtime, seed_auth_user

CLIENT_ID = "22222222-2222-2222-2222-222222222222"
OTHER_CLIENT_ID = "99999999-9999-9999-9999-999999999999"
LOCATION_ID = "33333333-3333-3333-3333-333333333333"
OTHER_LOCATION_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
USER_ID = "11111111-1111-1111-1111-111111111111"


def _setup_runtime(tmp_path: Path, monkeypatch):
    runtime = build_sqlite_runtime(tmp_path, "finance_reports.db")
    monkeypatch.setattr(deps, "settings", runtime.settings)
    seed_auth_user(
        runtime.session_factory,
        user_id=USER_ID,
        client_id=CLIENT_ID,
        email="owner@example.com",
        name="Owner",
        password_hash=hash_password("secret"),
        role_code="CLIENT_OWNER",
    )
    seed_auth_user(
        runtime.session_factory,
        user_id="bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
        client_id=OTHER_CLIENT_ID,
        email="noise@example.com",
        name="Noise",
        password_hash=hash_password("secret"),
        role_code="CLIENT_OWNER",
    )
    with runtime.session_factory() as session:
        session.add(
            ClientSettingsModel(
                client_settings_id=new_uuid(),
                client_id=CLIENT_ID,
                low_stock_threshold=Decimal("2"),
                allow_backorder=False,
                default_location_name="Main Warehouse",
                require_discount_approval=False,
                order_prefix="SO",
                purchase_prefix="PO",
                return_prefix="RT",
            )
        )
        session.add(
            LocationModel(
                location_id=LOCATION_ID,
                client_id=CLIENT_ID,
                name="Main Warehouse",
                code="MAIN",
                is_default=True,
                status="active",
            )
        )
        session.add(
            LocationModel(
                location_id=OTHER_LOCATION_ID,
                client_id=OTHER_CLIENT_ID,
                name="Noise Warehouse",
                code="NOISE",
                is_default=True,
                status="active",
            )
        )
        session.commit()
    return runtime


def _login_client() -> TestClient:
    client = TestClient(create_app())
    response = client.post("/auth/login", json={"email": "owner@example.com", "password": "secret"})
    assert response.status_code == 200
    return client


def _seed_reporting_fixture(runtime, *, base_at: datetime) -> None:
    purchase_at = base_at - timedelta(days=2)
    sale_at = base_at - timedelta(days=1)
    return_at = base_at

    with runtime.session_factory() as session:
        supplier = SupplierModel(
            supplier_id=new_uuid(),
            client_id=CLIENT_ID,
            name="Trusted Supplier",
            code="SUP-001",
            status="active",
        )
        category = CategoryModel(
            category_id=new_uuid(),
            client_id=CLIENT_ID,
            name="Footwear",
            slug="footwear",
            status="active",
        )
        customer = CustomerModel(
            customer_id=new_uuid(),
            client_id=CLIENT_ID,
            code="CUST-001",
            name="Amina Buyer",
            email="amina@example.com",
            status="active",
        )
        session.add_all([supplier, category, customer])
        session.flush()

        product_a = ProductModel(
            product_id=new_uuid(),
            client_id=CLIENT_ID,
            supplier_id=supplier.supplier_id,
            category_id=category.category_id,
            name="Trail Runner",
            slug="trail-runner",
            sku_root="TRAIL",
            brand="Easy Brand",
            status="active",
            default_price_amount=Decimal("100"),
            min_price_amount=Decimal("90"),
        )
        product_b = ProductModel(
            product_id=new_uuid(),
            client_id=CLIENT_ID,
            supplier_id=supplier.supplier_id,
            category_id=category.category_id,
            name="City Runner",
            slug="city-runner",
            sku_root="CITY",
            brand="Easy Brand",
            status="active",
            default_price_amount=Decimal("50"),
            min_price_amount=Decimal("45"),
        )
        session.add_all([product_a, product_b])
        session.flush()

        variant_a = ProductVariantModel(
            variant_id=new_uuid(),
            client_id=CLIENT_ID,
            product_id=product_a.product_id,
            title="42 / Black",
            sku="TRAIL-42-BLK",
            status="active",
            cost_amount=Decimal("40"),
            price_amount=Decimal("100"),
            min_price_amount=Decimal("90"),
            reorder_level=Decimal("2"),
        )
        variant_b = ProductVariantModel(
            variant_id=new_uuid(),
            client_id=CLIENT_ID,
            product_id=product_b.product_id,
            title="41 / White",
            sku="CITY-41-WHT",
            status="active",
            cost_amount=Decimal("25"),
            price_amount=Decimal("50"),
            min_price_amount=Decimal("45"),
            reorder_level=Decimal("5"),
        )
        session.add_all([variant_a, variant_b])
        session.flush()

        purchase = PurchaseModel(
            purchase_id=new_uuid(),
            client_id=CLIENT_ID,
            supplier_id=supplier.supplier_id,
            location_id=LOCATION_ID,
            purchase_number="PO-1001",
            status="received",
            ordered_at=purchase_at,
            received_at=purchase_at,
            subtotal_amount=Decimal("500"),
            total_amount=Decimal("500"),
            created_by_user_id=USER_ID,
        )
        session.add(purchase)
        session.flush()
        purchase_item_a = PurchaseItemModel(
            purchase_item_id=new_uuid(),
            client_id=CLIENT_ID,
            purchase_id=purchase.purchase_id,
            variant_id=variant_a.variant_id,
            quantity=Decimal("10"),
            received_quantity=Decimal("10"),
            unit_cost_amount=Decimal("40"),
            line_total_amount=Decimal("400"),
        )
        purchase_item_b = PurchaseItemModel(
            purchase_item_id=new_uuid(),
            client_id=CLIENT_ID,
            purchase_id=purchase.purchase_id,
            variant_id=variant_b.variant_id,
            quantity=Decimal("4"),
            received_quantity=Decimal("4"),
            unit_cost_amount=Decimal("25"),
            line_total_amount=Decimal("100"),
        )
        session.add_all([purchase_item_a, purchase_item_b])

        sales_order = SalesOrderModel(
            sales_order_id=new_uuid(),
            client_id=CLIENT_ID,
            customer_id=customer.customer_id,
            location_id=LOCATION_ID,
            order_number="SO-1001",
            status="completed",
            payment_status="partial",
            shipment_status="fulfilled",
            ordered_at=sale_at,
            confirmed_at=sale_at,
            subtotal_amount=Decimal("300"),
            total_amount=Decimal("300"),
            paid_amount=Decimal("250"),
            created_by_user_id=USER_ID,
        )
        session.add(sales_order)
        session.flush()
        sales_item_a = SalesOrderItemModel(
            sales_order_item_id=new_uuid(),
            client_id=CLIENT_ID,
            sales_order_id=sales_order.sales_order_id,
            variant_id=variant_a.variant_id,
            quantity=Decimal("2"),
            quantity_fulfilled=Decimal("2"),
            unit_price_amount=Decimal("100"),
            line_total_amount=Decimal("200"),
        )
        sales_item_b = SalesOrderItemModel(
            sales_order_item_id=new_uuid(),
            client_id=CLIENT_ID,
            sales_order_id=sales_order.sales_order_id,
            variant_id=variant_b.variant_id,
            quantity=Decimal("2"),
            quantity_fulfilled=Decimal("2"),
            unit_price_amount=Decimal("50"),
            line_total_amount=Decimal("100"),
        )
        session.add_all([sales_item_a, sales_item_b])

        sales_payment = PaymentModel(
            payment_id=new_uuid(),
            client_id=CLIENT_ID,
            sales_order_id=sales_order.sales_order_id,
            status="completed",
            method="cash",
            amount=Decimal("250"),
            paid_at=sale_at,
            reference="PAY-1001",
            created_by_user_id=USER_ID,
        )
        session.add(sales_payment)

        sales_return = SalesReturnModel(
            sales_return_id=new_uuid(),
            client_id=CLIENT_ID,
            sales_order_id=sales_order.sales_order_id,
            customer_id=customer.customer_id,
            return_number="RT-1001",
            status="received",
            refund_status="partial",
            requested_at=return_at,
            received_at=return_at,
            subtotal_amount=Decimal("100"),
            refund_amount=Decimal("100"),
            created_by_user_id=USER_ID,
        )
        session.add(sales_return)
        session.flush()
        session.add(
            SalesReturnItemModel(
                sales_return_item_id=new_uuid(),
                client_id=CLIENT_ID,
                sales_return_id=sales_return.sales_return_id,
                sales_order_item_id=sales_item_a.sales_order_item_id,
                variant_id=variant_a.variant_id,
                quantity=Decimal("1"),
                restock_quantity=Decimal("1"),
                unit_refund_amount=Decimal("100"),
                disposition="restock",
            )
        )
        session.add(
            PaymentModel(
                payment_id=new_uuid(),
                client_id=CLIENT_ID,
                sales_return_id=sales_return.sales_return_id,
                status="completed",
                method="cash",
                amount=Decimal("60"),
                paid_at=return_at,
                reference="RF-1001",
                created_by_user_id=USER_ID,
            )
        )

        session.add_all(
            [
                ExpenseModel(
                    expense_id=new_uuid(),
                    client_id=CLIENT_ID,
                    expense_number="EXP-1001",
                    category="rent",
                    description="Rent paid",
                    vendor_name="Landlord",
                    amount=Decimal("30"),
                    incurred_at=return_at,
                    payment_status="paid",
                    created_by_user_id=USER_ID,
                ),
                ExpenseModel(
                    expense_id=new_uuid(),
                    client_id=CLIENT_ID,
                    expense_number="EXP-1002",
                    category="utilities",
                    description="Power bill accrued",
                    vendor_name="Utility",
                    amount=Decimal("20"),
                    incurred_at=return_at,
                    payment_status="unpaid",
                    created_by_user_id=USER_ID,
                ),
            ]
        )

        session.add_all(
            [
                InventoryLedgerModel(
                    entry_id=new_uuid(),
                    client_id=CLIENT_ID,
                    variant_id=variant_a.variant_id,
                    location_id=LOCATION_ID,
                    movement_type="stock_received",
                    reference_type="purchase",
                    reference_id=str(purchase.purchase_id),
                    reference_line_id=str(purchase_item_a.purchase_item_id),
                    quantity_delta=Decimal("10"),
                    unit_cost_amount=Decimal("40"),
                    unit_price_amount=Decimal("100"),
                    reason="Purchase receipt",
                    created_by_user_id=USER_ID,
                    created_at=purchase_at,
                ),
                InventoryLedgerModel(
                    entry_id=new_uuid(),
                    client_id=CLIENT_ID,
                    variant_id=variant_b.variant_id,
                    location_id=LOCATION_ID,
                    movement_type="stock_received",
                    reference_type="purchase",
                    reference_id=str(purchase.purchase_id),
                    reference_line_id=str(purchase_item_b.purchase_item_id),
                    quantity_delta=Decimal("4"),
                    unit_cost_amount=Decimal("25"),
                    unit_price_amount=Decimal("50"),
                    reason="Purchase receipt",
                    created_by_user_id=USER_ID,
                    created_at=purchase_at,
                ),
                InventoryLedgerModel(
                    entry_id=new_uuid(),
                    client_id=CLIENT_ID,
                    variant_id=variant_a.variant_id,
                    location_id=LOCATION_ID,
                    movement_type="sale_fulfilled",
                    reference_type="sales_order",
                    reference_id=str(sales_order.sales_order_id),
                    reference_line_id=str(sales_item_a.sales_order_item_id),
                    quantity_delta=Decimal("-2"),
                    unit_cost_amount=Decimal("40"),
                    unit_price_amount=Decimal("100"),
                    reason="Order fulfilled",
                    created_by_user_id=USER_ID,
                    created_at=sale_at,
                ),
                InventoryLedgerModel(
                    entry_id=new_uuid(),
                    client_id=CLIENT_ID,
                    variant_id=variant_b.variant_id,
                    location_id=LOCATION_ID,
                    movement_type="sale_fulfilled",
                    reference_type="sales_order",
                    reference_id=str(sales_order.sales_order_id),
                    reference_line_id=str(sales_item_b.sales_order_item_id),
                    quantity_delta=Decimal("-2"),
                    unit_cost_amount=Decimal("25"),
                    unit_price_amount=Decimal("50"),
                    reason="Order fulfilled",
                    created_by_user_id=USER_ID,
                    created_at=sale_at,
                ),
                InventoryLedgerModel(
                    entry_id=new_uuid(),
                    client_id=CLIENT_ID,
                    variant_id=variant_a.variant_id,
                    location_id=LOCATION_ID,
                    movement_type="sales_return_restock",
                    reference_type="sales_return",
                    reference_id=str(sales_return.sales_return_id),
                    reference_line_id=None,
                    quantity_delta=Decimal("1"),
                    unit_cost_amount=Decimal("40"),
                    unit_price_amount=Decimal("100"),
                    reason="Restocked return",
                    created_by_user_id=USER_ID,
                    created_at=return_at,
                ),
            ]
        )

        noise_supplier = SupplierModel(
            supplier_id=new_uuid(),
            client_id=OTHER_CLIENT_ID,
            name="Noise Supplier",
            code="SUP-NOISE",
            status="active",
        )
        noise_category = CategoryModel(
            category_id=new_uuid(),
            client_id=OTHER_CLIENT_ID,
            name="Noise",
            slug="noise",
            status="active",
        )
        session.add_all([noise_supplier, noise_category])
        session.flush()
        noise_product = ProductModel(
            product_id=new_uuid(),
            client_id=OTHER_CLIENT_ID,
            supplier_id=noise_supplier.supplier_id,
            category_id=noise_category.category_id,
            name="Noise Product",
            slug="noise-product",
            sku_root="NOISE",
            brand="Noise",
            status="active",
            default_price_amount=Decimal("9999"),
        )
        session.add(noise_product)
        session.flush()
        noise_variant = ProductVariantModel(
            variant_id=new_uuid(),
            client_id=OTHER_CLIENT_ID,
            product_id=noise_product.product_id,
            title="One Size",
            sku="NOISE-001",
            status="active",
            cost_amount=Decimal("1"),
            price_amount=Decimal("9999"),
            reorder_level=Decimal("1"),
        )
        session.add(noise_variant)
        session.flush()
        noise_order = SalesOrderModel(
            sales_order_id=new_uuid(),
            client_id=OTHER_CLIENT_ID,
            location_id=OTHER_LOCATION_ID,
            order_number="SO-NOISE",
            status="completed",
            payment_status="paid",
            shipment_status="fulfilled",
            ordered_at=sale_at,
            confirmed_at=sale_at,
            subtotal_amount=Decimal("9999"),
            total_amount=Decimal("9999"),
            paid_amount=Decimal("9999"),
        )
        session.add(noise_order)
        session.flush()
        session.add(
            SalesOrderItemModel(
                sales_order_item_id=new_uuid(),
                client_id=OTHER_CLIENT_ID,
                sales_order_id=noise_order.sales_order_id,
                variant_id=noise_variant.variant_id,
                quantity=Decimal("1"),
                quantity_fulfilled=Decimal("1"),
                unit_price_amount=Decimal("9999"),
                line_total_amount=Decimal("9999"),
            )
        )
        session.commit()


def test_reports_reconcile_from_variant_first_sources(monkeypatch, tmp_path: Path) -> None:
    runtime = _setup_runtime(tmp_path, monkeypatch)
    base_at = datetime.utcnow().replace(microsecond=0)
    _seed_reporting_fixture(runtime, base_at=base_at)
    client = _login_client()
    from_date = (base_at - timedelta(days=2)).date().isoformat()
    to_date = base_at.date().isoformat()

    overview = client.get("/reports/overview", params={"from_date": from_date, "to_date": to_date})
    assert overview.status_code == 200
    assert overview.json() == {
        "from_date": from_date,
        "to_date": to_date,
        "sales_revenue_total": 300.0,
        "sales_count": 1,
        "expense_total": 50.0,
        "returns_total": 1,
        "purchases_total": 500.0,
    }

    sales = client.get("/reports/sales", params={"from_date": from_date, "to_date": to_date})
    assert sales.status_code == 200
    sales_payload = sales.json()
    assert sales_payload["sales_count"] == 1
    assert sales_payload["revenue_total"] == 300.0
    assert sales_payload["top_products"][0] == {
        "product_id": sales_payload["top_products"][0]["product_id"],
        "product_name": "Trail Runner",
        "qty_sold": 2,
        "revenue": 200.0,
    }
    assert sales_payload["top_customers"] == [
        {
            "customer_id": sales_payload["top_customers"][0]["customer_id"],
            "customer_name": "Amina Buyer",
            "sales_count": 1,
            "revenue": 300.0,
        }
    ]

    inventory = client.get("/reports/inventory", params={"from_date": from_date, "to_date": to_date})
    assert inventory.status_code == 200
    inventory_payload = inventory.json()
    assert inventory_payload["total_skus_with_stock"] == 2
    assert inventory_payload["total_stock_units"] == 11
    assert inventory_payload["inventory_value"] == 410.0
    assert inventory_payload["low_stock_items"] == [
        {
            "product_id": inventory_payload["low_stock_items"][0]["product_id"],
            "product_name": "City Runner",
            "variant_id": inventory_payload["low_stock_items"][0]["variant_id"],
            "variant_label": "41 / White",
            "sku": "CITY-41-WHT",
            "current_qty": 2,
        }
    ]

    purchases = client.get("/reports/purchases", params={"from_date": from_date, "to_date": to_date})
    assert purchases.status_code == 200
    assert purchases.json()["purchases_subtotal"] == 500.0
    assert purchases.json()["purchases_count"] == 1

    returns = client.get("/reports/returns", params={"from_date": from_date, "to_date": to_date})
    assert returns.status_code == 200
    assert returns.json()["returns_count"] == 1
    assert returns.json()["return_qty_total"] == 1
    assert returns.json()["return_amount_total"] == 100.0

    products = client.get("/reports/products", params={"from_date": from_date, "to_date": to_date})
    assert products.status_code == 200
    assert products.json()["highest_selling"][0]["product_name"] == "Trail Runner"

    finance = client.get("/reports/finance", params={"from_date": from_date, "to_date": to_date})
    assert finance.status_code == 200
    finance_payload = finance.json()
    assert finance_payload["expense_total"] == 50.0
    assert finance_payload["receivables_total"] == 50.0
    assert finance_payload["payables_total"] is None
    assert finance_payload["net_operating_snapshot"] == -350.0
    assert finance_payload["deferred_metrics"] == [
        {
            "metric": "payables_total",
            "reason": "Disabled until supplier payment settlement is tracked canonically.",
        }
    ]


def test_finance_overview_is_tenant_scoped_and_cash_reconciled(monkeypatch, tmp_path: Path) -> None:
    runtime = _setup_runtime(tmp_path, monkeypatch)
    _seed_reporting_fixture(runtime, base_at=datetime.utcnow().replace(microsecond=0))
    client = _login_client()

    response = client.get("/finance/overview")
    assert response.status_code == 200
    assert response.json() == {
        "sales_revenue": 300.0,
        "expense_total": 50.0,
        "receivables": 50.0,
        "payables": None,
        "cash_in": 250.0,
        "cash_out": 90.0,
        "net_operating": 160.0,
    }


def test_static_finance_helper_routes_are_frozen(monkeypatch, tmp_path: Path) -> None:
    runtime = _setup_runtime(tmp_path, monkeypatch)
    _seed_reporting_fixture(runtime, base_at=datetime.utcnow().replace(microsecond=0))
    client = _login_client()

    accounts = client.get("/finance/accounts")
    assert accounts.status_code == 503

    reports = client.get("/finance/reports")
    assert reports.status_code == 503
