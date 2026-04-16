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
    ProductMediaModel,
    ProductModel,
    ProductVectorModel,
    ProductVariantModel,
    SupplierModel,
)
from easy_ecom.domain.services.product_media_service import ProductMediaService
from easy_ecom.tests.support.sqlite_runtime import build_sqlite_runtime, seed_auth_user


CLIENT_ID = "22222222-2222-2222-2222-222222222222"
LOCATION_ID = "33333333-3333-3333-3333-333333333333"
USER_ID = "11111111-1111-1111-1111-111111111111"


def _setup_runtime(tmp_path: Path, monkeypatch, *, role_code: str = "CLIENT_OWNER"):
    runtime = build_sqlite_runtime(tmp_path, "catalog.db")
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


def test_catalog_overview_requires_authentication(monkeypatch, tmp_path: Path):
    runtime = _setup_runtime(tmp_path, monkeypatch)
    client = TestClient(create_app())

    response = client.get("/catalog/overview")
    assert response.status_code == 401


def test_catalog_overview_requires_catalog_access(monkeypatch, tmp_path: Path):
    runtime = _setup_runtime(tmp_path, monkeypatch, role_code="SALES_AGENT")
    client = _login_client(runtime)

    response = client.get("/catalog/overview")
    assert response.status_code == 403


def test_catalog_overview_returns_module_overview(monkeypatch, tmp_path: Path):
    runtime = _setup_runtime(tmp_path, monkeypatch)
    client = _login_client(runtime)

    response = client.get("/catalog/overview")
    assert response.status_code == 200
    payload = response.json()
    assert payload["module"] == "catalog"  # API returns lowercase
    assert "status" in payload
    assert "summary" in payload
    assert "metrics" in payload


def test_catalog_workspace_returns_paginated_items(monkeypatch, tmp_path: Path):
    runtime = _setup_runtime(tmp_path, monkeypatch)
    # Seed two variants, one in stock, one out of stock
    _seed_variant(
        runtime,
        product_name="In Stock Item",
        sku="INSTOCK-001",
        size="M",
        color="Blue",
        stock_qty=Decimal("5"),
    )
    _seed_variant(
        runtime,
        product_name="Out of Stock Item",
        sku="OUTSTOCK-001",
        size="L",
        color="Red",
        stock_qty=Decimal("0"),
    )
    client = _login_client(runtime)

    # Default query (empty) should return only in stock items (include_oos=False by default)
    # This means products with at least one in-stock variant
    response = client.get("/catalog/workspace")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["items"]) == 1  # Only the in-stock product
    assert payload["items"][0]["name"] == "In Stock Item"  # Fixed: was "product_name"
    # Check that we have the expected structure (no pagination in this endpoint)
    assert "query" in payload
    assert "has_multiple_locations" in payload
    assert "active_location" in payload
    assert "locations" in payload
    assert "categories" in payload
    assert "suppliers" in payload
    assert "items" in payload
    # The in-stock product should have exactly one variant (the in-stock one)
    assert len(payload["items"][0]["variants"]) == 1
    assert payload["items"][0]["variants"][0]["sku"] == "INSTOCK-001"

    # With include_oos=True, should return both products (in-stock and out-of-stock)
    response = client.get("/catalog/workspace", params={"include_oos": "true"})
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["items"]) == 2  # Both products
    # Check that we have the expected structure
    assert "query" in payload
    assert "has_multiple_locations" in payload
    assert "active_location" in payload
    assert "locations" in payload
    assert "categories" in payload
    assert "suppliers" in payload
    assert "items" in payload
    # First item should be the in-stock product
    assert payload["items"][0]["name"] == "In Stock Item"
    assert len(payload["items"][0]["variants"]) == 1
    assert payload["items"][0]["variants"][0]["sku"] == "INSTOCK-001"
    # Second item should be the out-of-stock product
    assert payload["items"][1]["name"] == "Out of Stock Item"
    assert len(payload["items"][1]["variants"]) == 1
    assert payload["items"][1]["variants"][0]["sku"] == "OUTSTOCK-001"

    # Search by query
    response = client.get("/catalog/workspace", params={"q": "In Stock"})
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["items"]) == 1
    # Find the variant with SKU INSTOCK-001
    variant_sku = None
    for item in payload["items"]:
        for variant in item["variants"]:
            if variant["sku"] == "INSTOCK-001":
                variant_sku = variant["sku"]
                break
        if variant_sku:
            break
    assert variant_sku == "INSTOCK-001"

    # Search by location_id (if we had multiple locations, but we only have one)
    # Without include_oos parameter, it defaults to False, so only in-stock products
    response = client.get("/catalog/workspace", params={"location_id": LOCATION_ID})
    assert response.status_code == 200
    payload = response.json()
    # Should still have 1 item (only in-stock product by default)
    assert len(payload["items"]) == 1


def test_catalog_create_product_success(monkeypatch, tmp_path: Path):
    runtime = _setup_runtime(tmp_path, monkeypatch)
    client = _login_client(runtime)

    response = client.post(
        "/catalog/products",
        json={
            "identity": {
                "product_name": "New Product",
                "supplier": "Test Supplier",
                "category": "Test Category",
                "sku_root": "NEW",
                "default_selling_price": "100",
                "min_selling_price": "90",
            },
            "variants": [
                {
                    "size": "M",
                    "color": "Blue",
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
    assert payload["product"]["name"] == "New Product"
    assert len(payload["product"]["variants"]) == 1
    variant = payload["product"]["variants"][0]
    assert variant["sku"] == "NEW-M-BLUE"
    # Check variant structure - size and color are in options
    assert variant["options"]["size"] == "M"  # Fixed: now checking correct field
    assert variant["options"]["color"] == "Blue"  # Fixed: now checking correct field


def test_catalog_staged_media_upload_endpoint(monkeypatch, tmp_path: Path):
    runtime = _setup_runtime(tmp_path, monkeypatch)
    client = _login_client(runtime)

    monkeypatch.setattr(
        ProductMediaService,
        "create_staged_upload",
        lambda self, session, client_id, user_id, upload_file: {
            "media_id": "media-1",
            "upload_id": "media-1",
            "large_url": "https://example.com/large.jpg",
            "thumbnail_url": "https://example.com/thumb.webp",
            "width": 768,
            "height": 768,
            "vector_status": "pending",
        },
    )

    response = client.post(
        "/catalog/media/staged",
        files={"image": ("shoe.jpg", b"fake-image", "image/jpeg")},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["upload_id"] == "media-1"
    assert payload["thumbnail_url"] == "https://example.com/thumb.webp"


def test_catalog_create_product_attaches_staged_media(monkeypatch, tmp_path: Path):
    runtime = _setup_runtime(tmp_path, monkeypatch)
    client = _login_client(runtime)
    staged_media_id = new_uuid()

    monkeypatch.setattr(ProductMediaService, "_move_object", lambda self, source_key, target_key, content_type: None)
    monkeypatch.setattr(
        ProductMediaService,
        "signed_url",
        lambda self, key, expires_in_seconds=3600: f"https://signed.example/{key}",
    )

    with runtime.session_factory() as session:
        session.add(
            ProductMediaModel(
                product_media_id=staged_media_id,
                client_id=CLIENT_ID,
                status="staged",
                role="primary",
                large_object_key=f"{CLIENT_ID}/product-media/staged/{staged_media_id}/image-768.jpg",
                thumbnail_object_key=f"{CLIENT_ID}/product-media/staged/{staged_media_id}/thumb-256.webp",
                checksum_sha256="abc123",
                uploaded_by_user_id=USER_ID,
            )
        )
        session.commit()

    response = client.post(
        "/catalog/products",
        json={
            "identity": {
                "product_name": "Photo Product",
                "supplier": "Test Supplier",
                "category": "Test Category",
                "sku_root": "PHOTO",
                "default_selling_price": "100",
                "min_selling_price": "90",
                "pending_primary_media_upload_id": staged_media_id,
            },
            "variants": [
                {
                    "size": "M",
                    "color": "Blue",
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
    assert payload["product"]["image"]["media_id"] == staged_media_id
    assert payload["product"]["image_url"].startswith("https://signed.example/")

    with runtime.session_factory() as session:
        product = session.execute(select(ProductModel).where(ProductModel.name == "Photo Product")).scalar_one()
        media = session.execute(
            select(ProductMediaModel).where(ProductMediaModel.product_media_id == staged_media_id)
        ).scalar_one()
        vector = session.execute(
            select(ProductVectorModel).where(ProductVectorModel.product_media_id == staged_media_id)
        ).scalar_one()
        assert str(product.primary_media_id) == staged_media_id
        assert media.status == "attached"
        assert str(media.product_id) == str(product.product_id)
        assert vector.status == "pending"


def test_catalog_create_product_validation_error(monkeypatch, tmp_path: Path):
    runtime = _setup_runtime(tmp_path, monkeypatch)
    client = _login_client(runtime)

    # Missing required fields
    response = client.post(
        "/catalog/products",
        json={
            "identity": {
                "product_name": "Incomplete Product",
                # missing supplier, category, sku_root, prices
            },
            "variants": [],
        },
    )
    # Fixed: The API returns 400 for missing required fields, not 422
    assert response.status_code == 400  # Bad Request

    # Invalid price (below min)
    response = client.post(
        "/catalog/products",
        json={
            "identity": {
                "product_name": "Invalid Price Product",
                "supplier": "Test",
                "category": "Test",
                "sku_root": "INV",
                "default_selling_price": "10",
                "min_selling_price": "20",  # min > default
            },
            "variants": [
                {
                    "size": "M",
                    "color": "Blue",
                    "default_purchase_price": "50",
                    "default_selling_price": "100",
                    "min_selling_price": "90",
                }
            ],
        },
    )
    assert response.status_code == 400  # Bad Request from business logic




def test_catalog_validate_step_enforces_first_variant_details(monkeypatch, tmp_path: Path):
    runtime = _setup_runtime(tmp_path, monkeypatch)
    client = _login_client(runtime)

    invalid_response = client.post(
        "/catalog/products/validate-step",
        json={
            "step": "first_variant",
            "identity": {
                "product_name": "Wizard Product",
            },
            "variants": [
                {
                    "size": "",
                    "color": "",
                    "other": "",
                    "barcode": "",
                }
            ],
        },
    )
    assert invalid_response.status_code == 400
    assert "First variant details are required" in invalid_response.json()["error"]["message"]

    valid_response = client.post(
        "/catalog/products/validate-step",
        json={
            "step": "first_variant",
            "identity": {
                "product_name": "Wizard Product",
            },
            "variants": [
                {
                    "size": "M",
                    "color": "",
                    "other": "",
                    "barcode": "",
                }
            ],
        },
    )
    assert valid_response.status_code == 200
    assert valid_response.json() == {"step": "first_variant", "valid": True}

def test_catalog_update_product_success(monkeypatch, tmp_path: Path):
    runtime = _setup_runtime(tmp_path, monkeypatch)
    seeded = _seed_variant(
        runtime,
        product_name="Update Me",
        sku="UPD-001",
        size="S",
        color="Green",
        stock_qty=Decimal("3"),
    )
    client = _login_client(runtime)

    # Get the product ID from the seeded variant
    with runtime.session_factory() as session:
        product = session.execute(
            select(ProductModel).where(ProductVariantModel.variant_id == seeded["variant_id"])
        ).scalar_one()
        product_id = str(product.product_id)

    response = client.put(
        f"/catalog/products/{product_id}",
        json={
            "product_id": product_id,
            "identity": {
                "product_name": "Updated Product",
                "supplier": "Updated Supplier",
                "category": "Updated Category",
                "sku_root": "UPD",
                "default_selling_price": "150",
                "min_selling_price": "140",
            },
            "variants": [
                {
                    "variant_id": seeded["variant_id"],
                    "size": "S",
                    "color": "Yellow",  # changed color
                    "default_purchase_price": "60",
                    "default_selling_price": "150",
                    "min_selling_price": "140",
                    "reorder_level": "3",
                }
            ],
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["product"]["name"] == "Updated Product"
    variant = payload["product"]["variants"][0]
    # Note: The API preserves the original SKU when updating variants
    # So we expect the original SKU to remain unchanged
    assert variant["sku"] == "UPD-001"  # SKU remains the same as originally seeded
    assert variant["options"]["color"] == "Yellow"  # Fixed: now checking correct field


def test_catalog_update_product_not_found(monkeypatch, tmp_path: Path):
    runtime = _setup_runtime(tmp_path, monkeypatch)
    client = _login_client(runtime)

    fake_id = "00000000-0000-0000-0000-000000000000"
    response = client.put(
        f"/catalog/products/{fake_id}",
        json={
            "product_id": fake_id,
            "identity": {
                "product_name": "Non-existent",
                "supplier": "Test",
                "category": "Test",
                "sku_root": "TEST",
                "default_selling_price": "100",
                "min_selling_price": "90",
            },
            "variants": [
                {
                    "size": "M",
                    "color": "Blue",
                    "default_purchase_price": "50",
                    "default_selling_price": "100",
                    "min_selling_price": "90",
                }
            ],
        },
    )
    assert response.status_code == 404


def test_catalog_update_product_unauthorized(monkeypatch, tmp_path: Path):
    runtime = _setup_runtime(tmp_path, monkeypatch, role_code="SALES_AGENT")
    seeded = _seed_variant(
        runtime,
        product_name="Update Me",
        sku="UPD-002",
        size="L",
        color="Black",
        stock_qty=Decimal("1"),
    )
    client = _login_client(runtime)

    with runtime.session_factory() as session:
        product = session.execute(
            select(ProductModel).where(ProductVariantModel.variant_id == seeded["variant_id"])
        ).scalar_one()
        product_id = str(product.product_id)

    response = client.put(
        f"/catalog/products/{product_id}",
        json={
            "product_id": product_id,
            "identity": {
                "product_name": "Hacked Product",
                "supplier": "Hacker",
                "category": "Hacked",
                "sku_root": "HACK",
                "default_selling_price": "1000",
                "min_selling_price": "900",
            },
            "variants": [
                {
                    "variant_id": seeded["variant_id"],
                    "size": "L",
                    "color": "Black",
                    "default_purchase_price": "500",
                    "default_selling_price": "1000",
                    "min_selling_price": "900",
                }
            ],
        },
    )
    assert response.status_code == 403
