from __future__ import annotations

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
    InventoryLedgerModel,
    LocationModel,
    ProductModel,
    ProductVariantModel,
    SupplierModel,
)
from easy_ecom.tests.support.sqlite_runtime import build_sqlite_runtime, seed_auth_user


CLIENT_ID = "22222222-2222-2222-2222-222222222222"
LOCATION_ID = "33333333-3333-3333-3333-333333333333"
USER_ID = "11111111-1111-1111-1111-111111111111"


def _setup_runtime(tmp_path: Path, monkeypatch, *, role_code: str = "CLIENT_OWNER"):
    runtime = build_sqlite_runtime(tmp_path, "commerce.db")
    monkeypatch.setattr(deps, "settings", runtime.settings)
    seed_auth_user(
        runtime.session_factory,
        user_id=USER_ID,
        client_id=CLIENT_ID,
        email="owner@example.com",
        name="Owner",
        password_hash=hash_password("secret"),
        role_code=role_code,
    )
    with runtime.session_factory() as session:
        if session.execute(
            select(ClientSettingsModel).where(ClientSettingsModel.client_id == CLIENT_ID)
        ).scalar_one_or_none() is None:
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
        if session.execute(
            select(LocationModel).where(LocationModel.client_id == CLIENT_ID, LocationModel.location_id == LOCATION_ID)
        ).scalar_one_or_none() is None:
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
        session.commit()
    return runtime


def _login_client(runtime) -> TestClient:
    client = TestClient(create_app())
    response = client.post("/auth/login", json={"email": "owner@example.com", "password": "secret"})
    assert response.status_code == 200
    return client


def _seed_variant(
    runtime,
    *,
    product_name: str,
    sku: str,
    size: str,
    color: str,
    stock_qty: Decimal,
    reorder_level: Decimal = Decimal("1"),
) -> dict[str, str]:
    with runtime.session_factory() as session:
        supplier = SupplierModel(
            supplier_id=new_uuid(),
            client_id=CLIENT_ID,
            name="Default Supplier",
            code=f"SUP-{sku[:6]}",
            status="active",
        )
        category = CategoryModel(
            category_id=new_uuid(),
            client_id=CLIENT_ID,
            name="Footwear",
            slug=f"footwear-{sku[:4].lower()}",
            status="active",
        )
        product = ProductModel(
            product_id=new_uuid(),
            client_id=CLIENT_ID,
            supplier_id=supplier.supplier_id,
            category_id=category.category_id,
            name=product_name,
            slug=f"{product_name.lower().replace(' ', '-')}-{sku[:4].lower()}",
            sku_root=sku.split("-")[0],
            brand="Easy Brand",
            description=f"{product_name} description",
            status="active",
            default_price_amount=Decimal("75"),
            min_price_amount=Decimal("65"),
            max_discount_percent=Decimal("10"),
        )
        variant = ProductVariantModel(
            variant_id=new_uuid(),
            client_id=CLIENT_ID,
            product_id=product.product_id,
            title=f"{size} / {color}",
            sku=sku,
            barcode=f"BC-{sku}",
            option_values_json={"size": size, "color": color, "other": ""},
            status="active",
            cost_amount=Decimal("40"),
            price_amount=Decimal("75"),
            min_price_amount=Decimal("65"),
            reorder_level=reorder_level,
        )
        session.add_all([supplier, category])
        session.flush()
        session.add_all([product, variant])
        session.flush()
        if stock_qty > 0:
            session.add(
                InventoryLedgerModel(
                    entry_id=new_uuid(),
                    client_id=CLIENT_ID,
                    variant_id=variant.variant_id,
                    location_id=LOCATION_ID,
                    movement_type="stock_received",
                    reference_type="seed",
                    reference_id=new_uuid(),
                    reference_line_id=None,
                    quantity_delta=stock_qty,
                    unit_cost_amount=Decimal("40"),
                    unit_price_amount=Decimal("75"),
                    reason="Seed stock",
                    created_by_user_id=USER_ID,
                )
            )
        session.commit()
        return {
            "product_id": str(product.product_id),
            "variant_id": str(variant.variant_id),
        }


def test_client_owner_no_longer_gets_customers_page(monkeypatch, tmp_path: Path):
    runtime = _setup_runtime(tmp_path, monkeypatch, role_code="CLIENT_OWNER")
    client = _login_client(runtime)

    me_response = client.get("/auth/me")
    assert me_response.status_code == 200
    assert "Customers" not in me_response.json()["allowed_pages"]

    denied_response = client.get("/customers/overview")
    assert denied_response.status_code == 403


def test_catalog_and_inventory_show_only_in_stock_variants(monkeypatch, tmp_path: Path):
    runtime = _setup_runtime(tmp_path, monkeypatch)
    in_stock = _seed_variant(
        runtime,
        product_name="Trail Runner",
        sku="TRAIL-42-BLK",
        size="42",
        color="Black",
        stock_qty=Decimal("5"),
    )
    _seed_variant(
        runtime,
        product_name="City Runner",
        sku="CITY-41-WHT",
        size="41",
        color="White",
        stock_qty=Decimal("0"),
    )
    client = _login_client(runtime)

    catalog_response = client.get("/catalog/workspace")
    assert catalog_response.status_code == 200
    catalog_payload = catalog_response.json()
    assert len(catalog_payload["items"]) == 1
    assert catalog_payload["items"][0]["product_id"] == in_stock["product_id"]
    assert catalog_payload["items"][0]["variants"][0]["label"] == "Trail Runner / 42 / Black"

    inventory_response = client.get("/inventory/workspace")
    assert inventory_response.status_code == 200
    inventory_payload = inventory_response.json()
    assert len(inventory_payload["stock_items"]) == 1
    assert inventory_payload["stock_items"][0]["variant_id"] == in_stock["variant_id"]
    assert inventory_payload["stock_items"][0]["available_to_sell"] == "5.000"


def test_sales_customer_lookup_dedupe_reservation_and_fulfillment(monkeypatch, tmp_path: Path):
    runtime = _setup_runtime(tmp_path, monkeypatch)
    seeded = _seed_variant(
        runtime,
        product_name="Trail Runner",
        sku="TRAIL-42-BLK",
        size="42",
        color="Black",
        stock_qty=Decimal("10"),
    )
    client = _login_client(runtime)

    create_response = client.post(
        "/sales/orders",
        json={
            "customer": {
                "name": "Walker One",
                "phone": "+971 55 123 4567",
                "email": "walker@example.com",
            },
            "lines": [
                {
                    "variant_id": seeded["variant_id"],
                    "quantity": "2",
                    "unit_price": "75",
                    "discount_amount": "0",
                }
            ],
            "action": "confirm",
        },
    )
    assert create_response.status_code == 200
    order = create_response.json()["order"]
    assert order["status"] == "confirmed"
    assert order["customer_phone"] == "+971 55 123 4567"
    assert order["lines"][0]["reserved_quantity"] == "2.000"

    customer_lookup = client.get("/sales/customers/search", params={"phone": "97155123"})
    assert customer_lookup.status_code == 200
    assert len(customer_lookup.json()["items"]) == 1

    draft_response = client.post(
        "/sales/orders",
        json={
            "customer": {
                "name": "Walker One Duplicate",
                "phone": "+971551234567",
                "email": "walker@example.com",
            },
            "lines": [
                {
                    "variant_id": seeded["variant_id"],
                    "quantity": "1",
                    "unit_price": "75",
                    "discount_amount": "0",
                }
            ],
            "action": "save_draft",
        },
    )
    assert draft_response.status_code == 200

    customers = runtime.store.read("customers.csv")
    assert len(customers) == 1

    inventory_reserved = client.get("/inventory/workspace")
    assert inventory_reserved.status_code == 200
    reserved_row = inventory_reserved.json()["stock_items"][0]
    assert reserved_row["on_hand"] == "10.000"
    assert reserved_row["reserved"] == "2.000"
    assert reserved_row["available_to_sell"] == "8.000"

    fulfill_response = client.post(f"/sales/orders/{order['sales_order_id']}/fulfill", json={})
    assert fulfill_response.status_code == 200
    fulfilled = fulfill_response.json()["order"]
    assert fulfilled["status"] == "completed"
    assert fulfilled["shipment_status"] == "fulfilled"

    inventory_fulfilled = client.get("/inventory/workspace")
    fulfilled_row = inventory_fulfilled.json()["stock_items"][0]
    assert fulfilled_row["on_hand"] == "8.000"
    assert fulfilled_row["reserved"] == "0"
    assert fulfilled_row["available_to_sell"] == "8.000"


def test_sales_rejects_oversell_and_returns_restock_inventory(monkeypatch, tmp_path: Path):
    runtime = _setup_runtime(tmp_path, monkeypatch)
    seeded = _seed_variant(
        runtime,
        product_name="Trail Runner",
        sku="TRAIL-42-BLK",
        size="42",
        color="Black",
        stock_qty=Decimal("3"),
    )
    client = _login_client(runtime)

    oversell_response = client.post(
        "/sales/orders",
        json={
            "customer": {
                "name": "Walker Two",
                "phone": "+971551111111",
                "email": "walker2@example.com",
            },
            "lines": [
                {
                    "variant_id": seeded["variant_id"],
                    "quantity": "4",
                    "unit_price": "75",
                    "discount_amount": "0",
                }
            ],
            "action": "confirm",
        },
    )
    assert oversell_response.status_code == 400

    create_response = client.post(
        "/sales/orders",
        json={
            "customer": {
                "name": "Walker Two",
                "phone": "+971551111111",
                "email": "walker2@example.com",
            },
            "lines": [
                {
                    "variant_id": seeded["variant_id"],
                    "quantity": "2",
                    "unit_price": "75",
                    "discount_amount": "0",
                }
            ],
            "action": "confirm_and_fulfill",
        },
    )
    assert create_response.status_code == 200
    order = create_response.json()["order"]
    assert order["status"] == "completed"

    eligible_orders = client.get("/returns/orders/search", params={"q": "971551111111"})
    assert eligible_orders.status_code == 200
    assert len(eligible_orders.json()["items"]) == 1

    eligible_lines = client.get(f"/returns/orders/{order['sales_order_id']}/eligible-lines")
    assert eligible_lines.status_code == 200
    line = eligible_lines.json()["lines"][0]
    assert line["eligible_quantity"] == "2.000"

    return_response = client.post(
        "/returns",
        json={
            "sales_order_id": order["sales_order_id"],
            "notes": "Customer returned one pair",
            "refund_status": "pending",
            "lines": [
                {
                    "sales_order_item_id": line["sales_order_item_id"],
                    "quantity": "1",
                    "restock_quantity": "1",
                    "disposition": "restock",
                    "unit_refund_amount": "75",
                    "reason": "Size exchange",
                }
            ],
        },
    )
    assert return_response.status_code == 200
    returned = return_response.json()
    assert returned["refund_amount"] == "75.00"

    inventory_after_return = client.get("/inventory/workspace")
    assert inventory_after_return.status_code == 200
    row = inventory_after_return.json()["stock_items"][0]
    assert row["on_hand"] == "2.000"
    assert row["available_to_sell"] == "2.000"

    eligible_after_return = client.get(f"/returns/orders/{order['sales_order_id']}/eligible-lines")
    assert eligible_after_return.status_code == 200
    assert eligible_after_return.json()["lines"][0]["eligible_quantity"] == "1.000"
