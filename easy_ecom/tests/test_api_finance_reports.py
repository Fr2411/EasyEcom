from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from easy_ecom.api import dependencies as deps
from easy_ecom.api.main import create_app
from easy_ecom.core.ids import new_uuid
from easy_ecom.core.security import hash_password
from easy_ecom.data.store.postgres_models import (
    CategoryModel,
    ClientSettingsModel,
    FinanceTransactionLinkModel,
    FinanceTransactionModel,
    LocationModel,
    ProductModel,
    ProductVariantModel,
    SupplierModel,
    InventoryLedgerModel,
)
from easy_ecom.tests.support.sqlite_runtime import build_sqlite_runtime, seed_auth_user

CLIENT_ID = "22222222-2222-2222-2222-222222222222"
OTHER_CLIENT_ID = "99999999-9999-9999-9999-999999999999"
LOCATION_ID = "33333333-3333-3333-3333-333333333333"
USER_ID = "11111111-1111-1111-1111-111111111111"


def _setup_runtime(tmp_path: Path, monkeypatch):
    runtime = build_sqlite_runtime(tmp_path, "finance_events.db")
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
    return runtime


def _login_client() -> TestClient:
    client = TestClient(create_app())
    response = client.post("/auth/login", json={"email": "owner@example.com", "password": "secret"})
    assert response.status_code == 200
    return client


def _seed_sales_fixture(runtime) -> dict[str, str]:
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
        location = LocationModel(
            location_id=LOCATION_ID,
            client_id=CLIENT_ID,
            name="Main Warehouse",
            code="MAIN",
            is_default=True,
            status="active",
        )
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
        session.add_all([location, supplier, category])
        session.flush()

        product = ProductModel(
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
        session.add(product)
        session.flush()

        variant = ProductVariantModel(
            variant_id=new_uuid(),
            client_id=CLIENT_ID,
            product_id=product.product_id,
            title="42 / Black",
            sku="TRAIL-42-BLK",
            barcode="BAR-TRAIL-42",
            status="active",
            cost_amount=Decimal("40"),
            price_amount=Decimal("100"),
            min_price_amount=Decimal("90"),
            reorder_level=Decimal("2"),
        )
        session.add(variant)
        session.flush()

        session.add(
            InventoryLedgerModel(
                entry_id=new_uuid(),
                client_id=CLIENT_ID,
                variant_id=variant.variant_id,
                location_id=location.location_id,
                movement_type="stock_received",
                reference_type="seed",
                reference_id=str(product.product_id),
                reference_line_id=None,
                quantity_delta=Decimal("5"),
                unit_cost_amount=Decimal("40"),
                unit_price_amount=Decimal("100"),
                reason="Seed stock",
                created_by_user_id=USER_ID,
            )
        )
        session.commit()
        return {
            "location_id": str(location.location_id),
            "variant_id": str(variant.variant_id),
        }


def _create_and_fulfill_order(client: TestClient, *, location_id: str, variant_id: str) -> dict:
    response = client.post(
        "/sales/orders",
        json={
            "location_id": location_id,
            "customer": {
                "name": "Amina Buyer",
                "phone": "+971500000111",
                "email": "amina@example.com",
                "address": "Dubai",
            },
            "payment_status": "unpaid",
            "shipment_status": "pending",
            "notes": "Fulfill for finance posting",
            "lines": [
                {
                    "variant_id": variant_id,
                    "quantity": "2",
                    "unit_price": "100",
                    "discount_amount": "0",
                }
            ],
            "action": "confirm_and_fulfill",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["order"]


def test_fulfilling_sales_orders_posts_finance_once_and_updates_overview(monkeypatch, tmp_path: Path) -> None:
    runtime = _setup_runtime(tmp_path, monkeypatch)
    fixture = _seed_sales_fixture(runtime)
    client = _login_client()

    order = _create_and_fulfill_order(client, **fixture)
    assert order["status"] == "completed"
    assert order["shipment_status"] == "fulfilled"
    assert order["finance_status"] == "posted"
    assert float(order["finance_summary"]["amount"]) == 200.0

    with runtime.session_factory() as session:
        transaction_count = session.execute(
            select(func.count()).select_from(FinanceTransactionModel).where(
                FinanceTransactionModel.client_id == CLIENT_ID,
                FinanceTransactionModel.origin_type == "sale_fulfillment",
                FinanceTransactionModel.origin_id == order["sales_order_id"],
            )
        ).scalar_one()
        link_count = session.execute(
            select(func.count()).select_from(FinanceTransactionLinkModel).where(
                FinanceTransactionLinkModel.client_id == CLIENT_ID,
                FinanceTransactionLinkModel.origin_type == "sale_fulfillment",
                FinanceTransactionLinkModel.origin_id == order["sales_order_id"],
            )
        ).scalar_one()
        assert transaction_count == 1
        assert link_count == 1

    refetched = client.get(f"/sales/orders/{order['sales_order_id']}")
    assert refetched.status_code == 200

    with runtime.session_factory() as session:
        transaction_count = session.execute(
            select(func.count()).select_from(FinanceTransactionModel).where(
                FinanceTransactionModel.client_id == CLIENT_ID,
                FinanceTransactionModel.origin_type == "sale_fulfillment",
                FinanceTransactionModel.origin_id == order["sales_order_id"],
            )
        ).scalar_one()
        assert transaction_count == 1

    overview = client.get("/finance/overview")
    assert overview.status_code == 200
    assert overview.json() == {
        "revenue": 200.0,
        "cash_collected": 0.0,
        "refunds_paid": 0.0,
        "expenses": 0.0,
        "receivables": 200.0,
        "payables": 0.0,
        "cash_in": 0.0,
        "cash_out": 0.0,
        "net_operating": 0.0,
    }


def test_order_payments_reduce_receivables_without_changing_recognized_revenue(monkeypatch, tmp_path: Path) -> None:
    runtime = _setup_runtime(tmp_path, monkeypatch)
    fixture = _seed_sales_fixture(runtime)
    client = _login_client()

    order = _create_and_fulfill_order(client, **fixture)
    payment_response = client.post(
        f"/sales/orders/{order['sales_order_id']}/record-payment",
        json={
            "payment_date": datetime.utcnow().isoformat(),
            "amount": "75",
            "method": "cash",
            "reference": "PAY-1001",
            "note": "Partial collection",
        },
    )
    assert payment_response.status_code == 200, payment_response.text
    updated_order = payment_response.json()["order"]
    assert updated_order["payment_status"] == "partial"
    assert float(updated_order["paid_amount"]) == 75.0

    overview = client.get("/finance/overview")
    assert overview.status_code == 200
    assert overview.json()["revenue"] == 200.0
    assert overview.json()["cash_collected"] == 75.0
    assert overview.json()["receivables"] == 125.0


def test_returns_post_finance_only_when_refund_is_paid(monkeypatch, tmp_path: Path) -> None:
    runtime = _setup_runtime(tmp_path, monkeypatch)
    fixture = _seed_sales_fixture(runtime)
    client = _login_client()

    order = _create_and_fulfill_order(client, **fixture)
    return_response = client.post(
        "/returns",
        json={
            "sales_order_id": order["sales_order_id"],
            "notes": "Customer returned one pair",
            "refund_status": "pending",
            "lines": [
                {
                    "sales_order_item_id": order["lines"][0]["sales_order_item_id"],
                    "quantity": "1",
                    "restock_quantity": "1",
                    "disposition": "restock",
                    "unit_refund_amount": "100",
                    "reason": "Damaged box",
                }
            ],
        },
    )
    assert return_response.status_code == 200, return_response.text
    sales_return = return_response.json()
    assert sales_return["finance_status"] == "not_posted"
    assert float(sales_return["refund_paid_amount"]) == 0.0
    assert float(sales_return["refund_outstanding_amount"]) == 100.0

    with runtime.session_factory() as session:
        refund_transactions = session.execute(
            select(func.count()).select_from(FinanceTransactionModel).where(
                FinanceTransactionModel.client_id == CLIENT_ID,
                FinanceTransactionModel.origin_type == "return_refund",
                FinanceTransactionModel.origin_id == sales_return["sales_return_id"],
            )
        ).scalar_one()
        assert refund_transactions == 0

    refund_one = client.post(
        f"/returns/{sales_return['sales_return_id']}/record-refund",
        json={
            "refund_date": datetime.utcnow().isoformat(),
            "amount": "40",
            "method": "bank transfer",
            "reference": "RF-1001",
            "note": "First refund payout",
        },
    )
    assert refund_one.status_code == 200, refund_one.text
    refund_payload = refund_one.json()
    assert refund_payload["refund_status"] == "partial"
    assert refund_payload["finance_status"] == "posted"
    assert float(refund_payload["refund_paid_amount"]) == 40.0
    assert float(refund_payload["refund_outstanding_amount"]) == 60.0
    assert len(refund_payload["recent_refunds"]) == 1

    refund_two = client.post(
        f"/returns/{sales_return['sales_return_id']}/record-refund",
        json={
            "refund_date": datetime.utcnow().isoformat(),
            "amount": "60",
            "method": "cash",
            "reference": "RF-1002",
            "note": "Final refund payout",
        },
    )
    assert refund_two.status_code == 200, refund_two.text
    refund_payload = refund_two.json()
    assert refund_payload["refund_status"] == "paid"
    assert float(refund_payload["refund_paid_amount"]) == 100.0
    assert float(refund_payload["refund_outstanding_amount"]) == 0.0
    assert len(refund_payload["recent_refunds"]) == 2

    with runtime.session_factory() as session:
        refund_transactions = session.execute(
            select(func.count()).select_from(FinanceTransactionModel).where(
                FinanceTransactionModel.client_id == CLIENT_ID,
                FinanceTransactionModel.origin_type == "return_refund",
                FinanceTransactionModel.origin_id == sales_return["sales_return_id"],
            )
        ).scalar_one()
        refund_links = session.execute(
            select(func.count()).select_from(FinanceTransactionLinkModel).where(
                FinanceTransactionLinkModel.client_id == CLIENT_ID,
                FinanceTransactionLinkModel.origin_type == "return_refund",
                FinanceTransactionLinkModel.origin_id == sales_return["sales_return_id"],
            )
        ).scalar_one()
        assert refund_transactions == 2
        assert refund_links == 2


def test_finance_workspace_splits_commerce_and_manual_transactions(monkeypatch, tmp_path: Path) -> None:
    runtime = _setup_runtime(tmp_path, monkeypatch)
    fixture = _seed_sales_fixture(runtime)
    client = _login_client()

    order = _create_and_fulfill_order(client, **fixture)
    manual_response = client.post(
        "/finance/transactions",
        json={
            "origin_type": "manual_expense",
            "occurred_at": datetime.utcnow().isoformat(),
            "amount": 35,
            "direction": "out",
            "status": "unpaid",
            "reference": "EXP-2001",
            "note": "Courier bill",
            "counterparty_name": "FastShip",
            "counterparty_type": "vendor",
        },
    )
    assert manual_response.status_code == 201, manual_response.text

    workspace = client.get("/finance/workspace")
    assert workspace.status_code == 200
    payload = workspace.json()

    assert payload["overview"]["revenue"] == 200.0
    assert payload["overview"]["expenses"] == 35.0
    assert payload["overview"]["payables"] == 35.0
    assert {item["origin_type"] for item in payload["commerce_transactions"]} == {"sale_fulfillment"}
    assert {item["origin_type"] for item in payload["manual_transactions"]} == {"manual_expense"}
    assert payload["commerce_transactions"][0]["editable"] is False
    assert payload["manual_transactions"][0]["editable"] is True
    assert payload["receivables"][0]["sale_id"] == order["sales_order_id"]
