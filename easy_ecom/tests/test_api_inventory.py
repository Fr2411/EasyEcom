from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import select

from easy_ecom.api import dependencies as deps
from easy_ecom.api.main import create_app
from easy_ecom.core.ids import new_uuid
from easy_ecom.core.security import hash_password
from easy_ecom.data.store.postgres_models import (
    CategoryModel,
    ClientSettingsModel,
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
    runtime = build_sqlite_runtime(tmp_path, "inventory.db")
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


def test_inventory_overview_requires_authentication(monkeypatch, tmp_path: Path):
    runtime = _setup_runtime(tmp_path, monkeypatch)
    client = TestClient(create_app())

    response = client.get("/inventory/overview")
    assert response.status_code == 401


def test_inventory_overview_requires_inventory_access(monkeypatch, tmp_path: Path):
    runtime = _setup_runtime(tmp_path, monkeypatch, role_code="SALES_AGENT")
    client = _login_client(runtime)

    response = client.get("/inventory/overview")
    assert response.status_code == 403


def test_inventory_overview_returns_module_overview(monkeypatch, tmp_path: Path):
    runtime = _setup_runtime(tmp_path, monkeypatch)
    client = _login_client(runtime)

    response = client.get("/inventory/overview")
    assert response.status_code == 200
    payload = response.json()
    assert payload["module"] == "inventory"  # API returns lowercase
    assert "status" in payload
    assert "summary" in payload
    assert "metrics" in payload


def test_inventory_workspace_returns_paginated_stock_items(monkeypatch, tmp_path: Path):
    runtime = _setup_runtime(tmp_path, monkeypatch)
    # Seed variants with different stock levels
    _seed_variant(
        runtime,
        product_name="In Stock Item",
        sku="INSTOCK-001",
        size="M",
        color="Blue",
        stock_qty=Decimal("10"),
    )
    _seed_variant(
        runtime,
        product_name="Low Stock Item",
        sku="LOWSTOCK-001",
        size="L",
        color="Red",
        stock_qty=Decimal("1"),  # Below low stock threshold of 2
    )
    _seed_variant(
        runtime,
        product_name="Out of Stock Item",
        sku="OUTSTOCK-001",
        size="XL",
        color="Green",
        stock_qty=Decimal("0"),
    )
    client = _login_client(runtime)

    # Default query should return stock items (available_to_sell > 0)
    response = client.get("/inventory/workspace")
    assert response.status_code == 200
    payload = response.json()
    # Check that we have the expected structure (no pagination in this endpoint)
    assert "query" in payload
    assert "has_multiple_locations" in payload
    assert "active_location" in payload
    assert "locations" in payload
    assert "stock_items" in payload
    assert "low_stock_items" in payload
    # Expect 2 stock items: in-stock (10) and low-stock (1)
    assert len(payload["stock_items"]) == 2
    # Check that the out-of-stock item (stock 0) is not in stock_items
    out_of_stock_skus = [item["sku"] for item in payload["stock_items"] if item["sku"] == "OUTSTOCK-001"]
    assert len(out_of_stock_skus) == 0
    # Check low stock items are identified (should be one)
    low_stock_items = [item for item in payload["stock_items"] if item["variant_id"] == "LOWSTOCK-001"]  # This won't work because variant_id is UUID
    # Instead, check by SKU
    low_stock_items = [item for item in payload["stock_items"] if item["sku"] == "LOWSTOCK-001"]
    assert len(low_stock_items) == 1
    assert low_stock_items[0]["available_to_sell"] == "1.000"
    assert float(low_stock_items[0]["available_to_sell"]) <= 2  # Below threshold

    # Search by query
    response = client.get("/inventory/workspace", params={"q": "In Stock"})
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["stock_items"]) == 1
    # Find the variant with SKU INSTOCK-001
    variant_sku = None
    for item in payload["stock_items"]:
        if item["sku"] == "INSTOCK-001":
            variant_sku = item["sku"]
            break
    assert variant_sku == "INSTOCK-001"


def test_inventory_intake_lookup_returns_matches(monkeypatch, tmp_path: Path):
    runtime = _setup_runtime(tmp_path, monkeypatch)
    seeded = _seed_variant(
        runtime,
        product_name="Test Product",
        sku="TEST-123",
        size="M",
        color="Blue",
        stock_qty=Decimal("5"),
    )
    client = _login_client(runtime)

    # Exact SKU match
    response = client.get("/inventory/intake/lookup", params={"q": "TEST-123"})
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["exact_variants"]) == 1
    assert payload["exact_variants"][0]["variant"]["sku"] == "TEST-123"
    assert payload["exact_variants"][0]["match_reason"] == "sku"

    # Product name match
    response = client.get("/inventory/intake/lookup", params={"q": "Test Product"})
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["product_matches"]) == 1
    assert payload["product_matches"][0]["name"] == "Test Product"

    # No matches
    response = client.get("/inventory/intake/lookup", params={"q": "Nonexistent"})
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["exact_variants"]) == 0
    assert len(payload["product_matches"]) == 0
    assert payload["suggested_new_product"]["product_name"] == "Nonexistent"


def test_inventory_low_stock_endpoint(monkeypatch, tmp_path: Path):
    runtime = _setup_runtime(tmp_path, monkeypatch)
    # Seed variants: one low stock, one OK, one out of stock
    _seed_variant(
        runtime,
        product_name="OK Stock",
        sku="OK-001",
        size="M",
        color="Blue",
        stock_qty=Decimal("5"),  # Above threshold
    )
    _seed_variant(
        runtime,
        product_name="Low Stock",
        sku="LOW-001",
        size="L",
        color="Red",
        stock_qty=Decimal("1"),  # Below threshold of 2
    )
    _seed_variant(
        runtime,
        product_name="Out of Stock",
        sku="OUT-001",
        size="XL",
        color="Green",
        stock_qty=Decimal("0"),
    )
    client = _login_client(runtime)

    response = client.get("/inventory/low-stock")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1  # Only one low stock item
    assert payload[0]["sku"] == "LOW-001"
    assert payload[0]["available_to_sell"] == "1.000"


def test_inventory_receive_stock_success(monkeypatch, tmp_path: Path):
    runtime = _setup_runtime(tmp_path, monkeypatch)
    client = _login_client(runtime)

    response = client.post(
        "/inventory/receipts",
        json={
            "action": "receive_stock",
            "location_id": LOCATION_ID,
            "notes": "Test receipt",
            "identity": {
                "product_name": "Received Product",
                "supplier": "Test Supplier",
                "category": "Test Category",
                "sku_root": "REC",
                "default_selling_price": "100",
                "min_selling_price": "90",
            },
            "lines": [
                {
                    "size": "M",
                    "color": "Blue",
                    "quantity": "10",
                    "default_purchase_price": "50",
                    "default_selling_price": "100",
                    "min_selling_price": "90",
                    "reorder_level": "2",
                }
            ],
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["action"] == "receive_stock"
    assert payload["purchase_id"] is not None
    assert len(payload["lines"]) == 1
    line = payload["lines"][0]
    assert line["quantity_received"] == "10"
    assert line["variant"]["sku"] == "REC-M-BLUE"

    # Verify inventory updated
    inventory_response = client.get("/inventory/workspace")
    assert inventory_response.status_code == 200
    inventory_payload = inventory_response.json()
    assert len(inventory_payload["stock_items"]) == 1
    assert inventory_payload["stock_items"][0]["available_to_sell"] == "10.000"


def test_inventory_receive_stock_validation_error(monkeypatch, tmp_path: Path):
    runtime = _setup_runtime(tmp_path, monkeypatch)
    client = _login_client(runtime)

    # Missing required fields
    response = client.post(
        "/inventory/receipts",
        json={
            "action": "receive_stock",
            # missing identity
            "lines": [],
        },
    )
    assert response.status_code == 422

    # Invalid action
    response = client.post(
        "/inventory/receipts",
        json={
            "action": "invalid_action",
            "identity": {
                "product_name": "Test",
                "supplier": "Test",
                "category": "Test",
                "sku_root": "TST",
                "default_selling_price": "100",
                "min_selling_price": "90",
            },
            "lines": [
                {
                    "size": "M",
                    "color": "Blue",
                    "quantity": "10",
                    "default_purchase_price": "50",
                    "default_selling_price": "100",
                    "min_selling_price": "90",
                }
            ],
        },
    )
    assert response.status_code == 422  # Bad request for invalid action


def test_inventory_adjust_stock_success(monkeypatch, tmp_path: Path):
    runtime = _setup_runtime(tmp_path, monkeypatch)
    # Seed a variant with initial stock
    seeded = _seed_variant(
        runtime,
        product_name="Adjustable Product",
        sku="ADJ-001",
        size="M",
        color="Blue",
        stock_qty=Decimal("10"),
    )
    client = _login_client(runtime)

    # Get variant ID
    with runtime.session_factory() as session:
        variant = session.execute(
            select(ProductVariantModel).where(ProductVariantModel.sku == "ADJ-001")
        ).scalar_one()
        variant_id = str(variant.variant_id)

    # Increase stock by 5
    response = client.post(
        "/inventory/adjustments",
        json={
            "location_id": LOCATION_ID,
            "variant_id": variant_id,
            "quantity_delta": "5",
            "reason": "restock",
            "notes": "Added more stock",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["available_to_sell"] == "15.000"  # 10 + 5

    # Decrease stock by 3
    response = client.post(
        "/inventory/adjustments",
        json={
            "location_id": LOCATION_ID,
            "variant_id": variant_id,
            "quantity_delta": "-3",
            "reason": "damage",
            "notes": "Removed damaged items",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["available_to_sell"] == "12.000"  # 15 - 3


def test_inventory_inline_update_updates_supplier_and_reorder_level(monkeypatch, tmp_path: Path):
    runtime = _setup_runtime(tmp_path, monkeypatch)
    _seed_variant(
        runtime,
        product_name="Inline Editable Product",
        sku="INLINE-001",
        size="M",
        color="Blue",
        stock_qty=Decimal("8"),
        reorder_level=Decimal("2"),
    )
    client = _login_client(runtime)

    with runtime.session_factory() as session:
        variant = session.execute(
            select(ProductVariantModel).where(ProductVariantModel.sku == "INLINE-001")
        ).scalar_one()
        variant_id = str(variant.variant_id)

    response = client.patch(
        "/inventory/inline-update",
        json={
            "variant_id": variant_id,
            "supplier": "Inline Supplier",
            "reorder_level": "5",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["supplier"] == "Inline Supplier"
    assert payload["reorder_level"] == "5.000"


def test_inventory_adjust_stock_validation_error(monkeypatch, tmp_path: Path):
    runtime = _setup_runtime(tmp_path, monkeypatch)
    seeded = _seed_variant(
        runtime,
        product_name="Test Product",
        sku="TST-001",
        size="M",
        color="Blue",
        stock_qty=Decimal("5"),
    )
    client = _login_client(runtime)

    with runtime.session_factory() as session:
        variant = session.execute(
            select(ProductVariantModel).where(ProductVariantModel.sku == "TST-001")
        ).scalar_one()
        variant_id = str(variant.variant_id)

    # Missing required fields
    response = client.post(
        "/inventory/adjustments",
        json={
            "location_id": LOCATION_ID,
            # missing variant_id
            "quantity_delta": "5",
        },
    )
    assert response.status_code == 422

    # Invalid quantity (not a number)
    response = client.post(
        "/inventory/adjustments",
        json={
            "location_id": LOCATION_ID,
            "variant_id": variant_id,
            "quantity_delta": "not_a_number",
        },
    )
    assert response.status_code == 422

    # Non-existent variant - API returns 422 for validation error, not 404
    response = client.post(
        "/inventory/adjustments",
        json={
            "location_id": LOCATION_ID,
            "variant_id": "00000000-0000-0000-0000-000000000000",
            "quantity_delta": "5",
        },
    )
    assert response.status_code == 422  # Validation error for invalid variant ID


def test_inventory_endpoints_require_authentication(monkeypatch, tmp_path: Path):
    runtime = _setup_runtime(tmp_path, monkeypatch)
    client = TestClient(create_app())

    endpoints = [
        ("/inventory/workspace", "GET"),
        ("/inventory/intake/lookup", "GET"),
        ("/inventory/low-stock", "GET"),
        ("/inventory/receipts", "POST"),
        ("/inventory/adjustments", "POST"),
        ("/inventory/inline-update", "PATCH"),
    ]

    for endpoint, method in endpoints:
        if method == "GET":
            response = client.get(endpoint)
        elif method == "POST":
            response = client.post(endpoint, json={})
        else:
            response = client.patch(endpoint, json={})
        assert response.status_code == 401, f"{endpoint} should require authentication"
