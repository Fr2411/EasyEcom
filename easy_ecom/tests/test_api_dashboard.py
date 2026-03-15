from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from sqlalchemy import select

from easy_ecom.core.ids import new_uuid
from easy_ecom.data.store.postgres_models import (
    CategoryModel,
    ClientSettingsModel,
    InventoryLedgerModel,
    LocationModel,
    ProductModel,
    ProductVariantModel,
    SupplierModel,
)
from easy_ecom.tests.test_api_commerce import CLIENT_ID, LOCATION_ID, _login_client, _seed_variant, _setup_runtime
from easy_ecom.tests.support.sqlite_runtime import seed_auth_user


OTHER_CLIENT_ID = "77777777-7777-7777-7777-777777777777"
OTHER_LOCATION_ID = "88888888-8888-8888-8888-888888888888"


def _metric_map(payload: dict[str, object]) -> dict[str, dict[str, object]]:
    return {item["id"]: item for item in payload["kpis"]}  # type: ignore[index]


def _create_completed_order(client, variant_id: str, *, quantity: str, unit_price: str, customer_name: str):
    response = client.post(
        "/sales/orders",
        json={
            "customer": {
                "name": customer_name,
                "phone": f"+97155{new_uuid()[:7]}",
                "email": f"{customer_name.lower().replace(' ', '')}@example.com",
            },
            "lines": [
                {
                    "variant_id": variant_id,
                    "quantity": quantity,
                    "unit_price": unit_price,
                    "discount_amount": "0",
                }
            ],
            "action": "confirm_and_fulfill",
        },
    )
    assert response.status_code == 200
    return response.json()["order"]


def _create_confirmed_order(client, variant_id: str, *, quantity: str, unit_price: str):
    response = client.post(
        "/sales/orders",
        json={
            "customer": {
                "name": "Reserved Walker",
                "phone": "+971551919191",
                "email": "reserved@example.com",
            },
            "lines": [
                {
                    "variant_id": variant_id,
                    "quantity": quantity,
                    "unit_price": unit_price,
                    "discount_amount": "0",
                }
            ],
            "action": "confirm",
        },
    )
    assert response.status_code == 200
    return response.json()["order"]


def _create_restock_return(client, order_id: str):
    eligible_lines = client.get(f"/returns/orders/{order_id}/eligible-lines")
    assert eligible_lines.status_code == 200
    line = eligible_lines.json()["lines"][0]
    response = client.post(
        "/returns",
        json={
            "sales_order_id": order_id,
            "notes": "Customer returned one unit",
            "refund_status": "pending",
            "lines": [
                {
                    "sales_order_item_id": line["sales_order_item_id"],
                    "quantity": "1",
                    "restock_quantity": "1",
                    "disposition": "restock",
                    "unit_refund_amount": line["unit_price"],
                    "reason": "Exchange",
                }
            ],
        },
    )
    assert response.status_code == 200
    return response.json()


def test_dashboard_analytics_owner_sees_financial_and_operational_insights(monkeypatch, tmp_path: Path):
    runtime = _setup_runtime(tmp_path, monkeypatch, role_code="CLIENT_OWNER")
    first = _seed_variant(
        runtime,
        product_name="Trail Runner",
        sku="TRAIL-42-BLK",
        size="42",
        color="Black",
        stock_qty=Decimal("10"),
        reorder_level=Decimal("2"),
    )
    second = _seed_variant(
        runtime,
        product_name="City Runner",
        sku="CITY-41-WHT",
        size="41",
        color="White",
        stock_qty=Decimal("6"),
        reorder_level=Decimal("4"),
    )
    _seed_variant(
        runtime,
        product_name="Canvas Classic",
        sku="CANVAS-40-NVY",
        size="40",
        color="Navy",
        stock_qty=Decimal("12"),
        reorder_level=Decimal("1"),
    )
    client = _login_client(runtime)

    first_order = _create_completed_order(
        client,
        first["variant_id"],
        quantity="2",
        unit_price="75",
        customer_name="Walker One",
    )
    _create_completed_order(
        client,
        second["variant_id"],
        quantity="1",
        unit_price="55",
        customer_name="Walker Two",
    )
    _create_confirmed_order(client, second["variant_id"], quantity="1", unit_price="55")
    _create_restock_return(client, first_order["sales_order_id"])

    response = client.get("/dashboard/analytics", params={"range_key": "mtd"})
    assert response.status_code == 200
    payload = response.json()
    metrics = _metric_map(payload)

    assert payload["visibility"]["can_view_financial_metrics"] is True
    assert payload["applied_range"]["range_key"] == "mtd"
    assert metrics["completed_sales_revenue"]["value"] == "205.00"
    assert metrics["estimated_gross_profit"]["value"] == "95.00"
    assert metrics["completed_orders"]["value"] == 2
    assert metrics["units_sold"]["value"] == "3.000"
    assert metrics["stock_on_hand_units"]["value"] == "26.000"
    assert metrics["low_stock_variants"]["value"] == 1
    assert payload["tables"]["low_stock_variants"][0]["product_name"] == "City Runner"
    assert payload["tables"]["top_products_by_estimated_gross_profit"]["items"][0]["product_name"] == "Trail Runner"
    assert payload["charts"]["product_opportunity_matrix"]["items"][0]["product_name"] == "Trail Runner"
    assert payload["charts"]["returns_trend"]["items"][-1]["refund_amount"] in {"0.00", "75.00"}
    assert any(card["id"] == "replenish_winners" for card in payload["insight_cards"])


def test_dashboard_analytics_staff_view_hides_financial_sections(monkeypatch, tmp_path: Path):
    runtime = _setup_runtime(tmp_path, monkeypatch, role_code="CLIENT_STAFF")
    seeded = _seed_variant(
        runtime,
        product_name="Trail Runner",
        sku="TRAIL-42-BLK",
        size="42",
        color="Black",
        stock_qty=Decimal("5"),
    )
    client = _login_client(runtime)
    _create_completed_order(
        client,
        seeded["variant_id"],
        quantity="1",
        unit_price="75",
        customer_name="Walker Staff",
    )
    _create_confirmed_order(client, seeded["variant_id"], quantity="1", unit_price="75")

    response = client.get("/dashboard/analytics", params={"range_key": "mtd"})
    assert response.status_code == 200
    payload = response.json()
    metrics = _metric_map(payload)

    assert payload["visibility"]["can_view_financial_metrics"] is False
    assert "completed_sales_revenue" not in metrics
    assert metrics["stock_received_units"]["value"] == "5.000"
    assert metrics["open_confirmed_orders"]["value"] == 1
    assert payload["charts"]["revenue_profit_trend"]["unavailable_reason"] == "Financial metrics are hidden for your role."
    assert payload["charts"]["product_opportunity_matrix"]["items"] == []
    assert payload["tables"]["top_products_by_revenue"]["items"] == []
    assert payload["tables"]["stock_investment_by_product"][0]["inventory_cost_value"] is None


def test_dashboard_analytics_remains_tenant_scoped(monkeypatch, tmp_path: Path):
    runtime = _setup_runtime(tmp_path, monkeypatch, role_code="CLIENT_OWNER")
    _seed_variant(
        runtime,
        product_name="Trail Runner",
        sku="TRAIL-42-BLK",
        size="42",
        color="Black",
        stock_qty=Decimal("5"),
    )
    client = _login_client(runtime)

    seed_auth_user(
        runtime.session_factory,
        user_id="99999999-9999-9999-9999-999999999999",
        client_id=OTHER_CLIENT_ID,
        email="other-owner@example.com",
        name="Other Owner",
        password_hash="hash",
        role_code="CLIENT_OWNER",
    )
    with runtime.session_factory() as session:
        session.add(
            ClientSettingsModel(
                client_settings_id=new_uuid(),
                client_id=OTHER_CLIENT_ID,
                low_stock_threshold=Decimal("2"),
                allow_backorder=False,
                default_location_name="Other Main",
                require_discount_approval=False,
                order_prefix="SO",
                purchase_prefix="PO",
                return_prefix="RT",
            )
        )
        session.add(
            LocationModel(
                location_id=OTHER_LOCATION_ID,
                client_id=OTHER_CLIENT_ID,
                name="Other Main",
                code="OTHER",
                is_default=True,
                status="active",
            )
        )
        supplier = SupplierModel(
            supplier_id=new_uuid(),
            client_id=OTHER_CLIENT_ID,
            name="Other Supplier",
            code="OTH-SUP",
            status="active",
        )
        category = CategoryModel(
            category_id=new_uuid(),
            client_id=OTHER_CLIENT_ID,
            name="Other Shoes",
            slug="other-shoes",
            status="active",
        )
        product = ProductModel(
            product_id=new_uuid(),
            client_id=OTHER_CLIENT_ID,
            supplier_id=supplier.supplier_id,
            category_id=category.category_id,
            name="Other Runner",
            slug="other-runner",
            sku_root="OTHER",
            brand="Other Brand",
            description="Other tenant stock",
            status="active",
            default_price_amount=Decimal("40"),
            min_price_amount=Decimal("30"),
            max_discount_percent=Decimal("10"),
        )
        variant = ProductVariantModel(
            variant_id=new_uuid(),
            client_id=OTHER_CLIENT_ID,
            product_id=product.product_id,
            title="43 / Blue",
            sku="OTHER-43-BLU",
            barcode="OTHER-BLU",
            option_values_json={"size": "43", "color": "Blue", "other": ""},
            status="active",
            cost_amount=Decimal("20"),
            price_amount=Decimal("40"),
            min_price_amount=Decimal("30"),
            reorder_level=Decimal("1"),
        )
        session.add_all([supplier, category, product, variant])
        session.flush()
        session.add(
            InventoryLedgerModel(
                entry_id=new_uuid(),
                client_id=OTHER_CLIENT_ID,
                variant_id=variant.variant_id,
                location_id=OTHER_LOCATION_ID,
                movement_type="stock_received",
                reference_type="seed",
                reference_id=new_uuid(),
                reference_line_id=None,
                quantity_delta=Decimal("100"),
                unit_cost_amount=Decimal("20"),
                unit_price_amount=Decimal("40"),
                reason="Other tenant stock",
                created_by_user_id="99999999-9999-9999-9999-999999999999",
            )
        )
        session.commit()

    response = client.get("/dashboard/analytics", params={"range_key": "mtd"})
    assert response.status_code == 200
    payload = response.json()
    metrics = _metric_map(payload)

    assert metrics["stock_on_hand_units"]["value"] == "5.000"
    assert all(row["product_name"] != "Other Runner" for row in payload["tables"]["stock_investment_by_product"])
