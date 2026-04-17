from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from datetime import datetime, UTC

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
    ProductMediaModel,
    ProductModel,
    ProductVariantModel,
    PurchaseItemModel,
    PurchaseModel,
    SupplierModel,
)
from easy_ecom.domain.services.product_media_service import ProductMediaService
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


def test_inventory_intake_lookup_returns_exact_variant_and_product_matches(monkeypatch, tmp_path: Path):
    runtime = _setup_runtime(tmp_path, monkeypatch)
    seeded = _seed_variant(
        runtime,
        product_name="Trail Runner",
        sku="TRAIL-42-BLK",
        size="42",
        color="Black",
        stock_qty=Decimal("0"),
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

    exact_response = client.get("/inventory/intake/lookup", params={"q": "TRAIL-42-BLK"})
    assert exact_response.status_code == 200
    exact_payload = exact_response.json()
    assert len(exact_payload["exact_variants"]) == 1
    assert exact_payload["exact_variants"][0]["match_reason"] == "sku"
    assert exact_payload["exact_variants"][0]["variant"]["variant_id"] == seeded["variant_id"]
    assert exact_payload["exact_variants"][0]["product"]["product_id"] == seeded["product_id"]

    product_response = client.get("/inventory/intake/lookup", params={"q": "Runner"})
    assert product_response.status_code == 200
    product_payload = product_response.json()
    assert product_payload["exact_variants"] == []
    assert len(product_payload["product_matches"]) == 2
    assert product_payload["suggested_new_product"]["product_name"] == "Runner"


def test_inventory_receipt_can_create_product_and_multiple_variant_lines(monkeypatch, tmp_path: Path):
    runtime = _setup_runtime(tmp_path, monkeypatch)
    client = _login_client(runtime)

    response = client.post(
        "/inventory/receipts",
        json={
            "action": "receive_stock",
            "notes": "New shipment arrived",
            "identity": {
                "product_name": "Canvas Sneaker",
                "supplier": "Fresh Supplier",
                "category": "Footwear",
                "sku_root": "CNVS",
                "default_selling_price": "65",
                "min_selling_price": "55",
            },
            "lines": [
                {
                    "size": "41",
                    "color": "Black",
                    "quantity": "5",
                    "default_purchase_price": "28",
                    "default_selling_price": "65",
                    "min_selling_price": "55",
                    "reorder_level": "2",
                },
                {
                    "size": "42",
                    "color": "Black",
                    "quantity": "3",
                    "default_purchase_price": "29",
                    "default_selling_price": "67",
                    "min_selling_price": "56",
                    "reorder_level": "2",
                },
            ],
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["action"] == "receive_stock"
    assert payload["purchase_id"]
    assert len(payload["lines"]) == 2
    assert {line["variant"]["sku"] for line in payload["lines"]} == {"CNVS-41-BLACK", "CNVS-42-BLACK"}

    with runtime.session_factory() as session:
        purchases = session.execute(select(PurchaseModel).where(PurchaseModel.client_id == CLIENT_ID)).scalars().all()
        assert len(purchases) == 1
        purchase_items = session.execute(select(PurchaseItemModel).where(PurchaseItemModel.client_id == CLIENT_ID)).scalars().all()
        assert len(purchase_items) == 2
        ledger_entries = session.execute(
            select(InventoryLedgerModel).where(
                InventoryLedgerModel.client_id == CLIENT_ID,
                InventoryLedgerModel.reference_type == "purchase",
            )
        ).scalars().all()
        assert len(ledger_entries) == 2

    inventory_response = client.get("/inventory/workspace")
    assert inventory_response.status_code == 200
    stock_items = inventory_response.json()["stock_items"]
    assert len(stock_items) == 2
    assert {item["available_to_sell"] for item in stock_items} == {"5.000", "3.000"}


def test_purchases_orders_default_load_handles_missing_reference_number_field(monkeypatch, tmp_path: Path):
    runtime = _setup_runtime(tmp_path, monkeypatch)
    client = _login_client(runtime)

    with runtime.session_factory() as session:
        supplier = SupplierModel(
            supplier_id=new_uuid(),
            client_id=CLIENT_ID,
            name="Source Supplier",
            code="SUP-PO-LIST",
            status="active",
        )
        purchase = PurchaseModel(
            purchase_id=new_uuid(),
            client_id=CLIENT_ID,
            supplier_id=supplier.supplier_id,
            location_id=LOCATION_ID,
            purchase_number="PO-TEST-001",
            status="received",
            ordered_at=datetime(2026, 4, 10, 10, 0, tzinfo=UTC),
            received_at=datetime(2026, 4, 11, 10, 0, tzinfo=UTC),
            notes="Legacy purchase row",
            created_by_user_id=USER_ID,
            subtotal_amount=Decimal("1250.00"),
            total_amount=Decimal("1250.00"),
        )
        session.add_all([supplier, purchase])
        session.commit()

    response = client.get("/purchases/orders")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["items"]) == 1
    assert payload["items"][0]["purchase_no"] == "PO-TEST-001"
    assert payload["items"][0]["reference_no"] == ""


def test_inventory_receipt_can_attach_staged_product_media(monkeypatch, tmp_path: Path):
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
        "/inventory/receipts",
        json={
            "action": "receive_stock",
            "notes": "New shipment with photo",
            "identity": {
                "product_name": "Photo Sneaker",
                "supplier": "Fresh Supplier",
                "category": "Footwear",
                "sku_root": "PIC",
                "default_selling_price": "65",
                "min_selling_price": "55",
                "pending_primary_media_upload_id": staged_media_id,
            },
            "lines": [
                {
                    "size": "41",
                    "color": "Black",
                    "quantity": "5",
                    "default_purchase_price": "28",
                    "default_selling_price": "65",
                    "min_selling_price": "55",
                    "reorder_level": "2",
                }
            ],
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["product"]["image"]["media_id"] == staged_media_id

    with runtime.session_factory() as session:
        product = session.execute(select(ProductModel).where(ProductModel.name == "Photo Sneaker")).scalar_one()
        assert str(product.primary_media_id) == staged_media_id


def test_inventory_template_save_adds_new_variant_without_stock_or_purchase(monkeypatch, tmp_path: Path):
    runtime = _setup_runtime(tmp_path, monkeypatch)
    seeded = _seed_variant(
        runtime,
        product_name="Trail Runner",
        sku="TRAIL-42-BLK",
        size="42",
        color="Black",
        stock_qty=Decimal("4"),
    )
    client = _login_client(runtime)

    response = client.post(
        "/inventory/receipts",
        json={
            "action": "save_template_only",
            "notes": "Preparing next size run",
            "identity": {
                "product_id": seeded["product_id"],
                "product_name": "Trail Runner Edited",
                "supplier": "Changed Supplier",
                "category": "Footwear",
                "sku_root": "TRAIL",
            },
            "lines": [
                {
                    "size": "43",
                    "color": "Black",
                    "default_purchase_price": "41",
                    "default_selling_price": "76",
                    "min_selling_price": "66",
                    "reorder_level": "1",
                }
            ],
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["action"] == "save_template_only"
    assert payload["purchase_id"] is None
    assert len(payload["lines"]) == 1
    assert payload["lines"][0]["quantity_received"] == "0"
    assert payload["lines"][0]["variant"]["sku"] == "TRAIL-43-BLACK"

    with runtime.session_factory() as session:
        product = session.execute(select(ProductModel).where(ProductModel.product_id == seeded["product_id"])).scalar_one()
        assert product.name == "Trail Runner"
        purchases = session.execute(select(PurchaseModel).where(PurchaseModel.client_id == CLIENT_ID)).scalars().all()
        assert purchases == []
        new_variant = session.execute(
            select(ProductVariantModel).where(
                ProductVariantModel.client_id == CLIENT_ID,
                ProductVariantModel.sku == "TRAIL-43-BLACK",
            )
        ).scalar_one()
        ledger_total = session.execute(
            select(InventoryLedgerModel).where(
                InventoryLedgerModel.client_id == CLIENT_ID,
                InventoryLedgerModel.variant_id == new_variant.variant_id,
            )
        ).scalars().all()
        assert ledger_total == []


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


def test_catalog_generates_sku_and_preserves_saved_variant_sku(monkeypatch, tmp_path: Path):
    runtime = _setup_runtime(tmp_path, monkeypatch)
    client = _login_client(runtime)

    create_response = client.post(
        "/catalog/products",
        json={
            "identity": {
                "product_name": "Trail Runner",
                "supplier": "Default Supplier",
                "category": "Footwear",
                "sku_root": "TRAIL",
                "default_selling_price": "75",
                "min_selling_price": "65",
            },
            "variants": [
                {
                    "size": "42",
                    "color": "Black",
                    "default_purchase_price": "40",
                    "default_selling_price": "75",
                    "min_selling_price": "65",
                    "reorder_level": "1",
                }
            ],
        },
    )
    assert create_response.status_code == 200
    product = create_response.json()["product"]
    variant = product["variants"][0]
    assert variant["sku"] == "TRAIL-42-BLACK"

    update_response = client.put(
        f"/catalog/products/{product['product_id']}",
        json={
            "product_id": product["product_id"],
            "identity": {
                "product_name": "Trail Runner",
                "supplier": "Default Supplier",
                "category": "Footwear",
                "sku_root": "TRAIL",
                "default_selling_price": "75",
                "min_selling_price": "65",
            },
            "variants": [
                {
                    "variant_id": variant["variant_id"],
                    "size": "42",
                    "color": "Navy",
                    "default_purchase_price": "40",
                    "default_selling_price": "75",
                    "min_selling_price": "65",
                    "reorder_level": "1",
                    "status": "active",
                }
            ],
        },
    )
    assert update_response.status_code == 200
    updated_variant = update_response.json()["product"]["variants"][0]
    assert updated_variant["sku"] == "TRAIL-42-BLACK"
    assert updated_variant["label"] == "Trail Runner / 42 / Navy"


def test_sales_search_uses_effective_price_and_rejects_below_minimum(monkeypatch, tmp_path: Path):
    runtime = _setup_runtime(tmp_path, monkeypatch)
    priced = _seed_variant(
        runtime,
        product_name="Trail Runner",
        sku="TRAIL-42-BLK",
        size="42",
        color="Black",
        stock_qty=Decimal("6"),
    )
    with runtime.session_factory() as session:
        priced_variant = session.execute(
            select(ProductVariantModel).where(ProductVariantModel.variant_id == priced["variant_id"])
        ).scalar_one()
        priced_variant.price_amount = None
        priced_variant.min_price_amount = None

        unpriced_product = ProductModel(
            product_id=new_uuid(),
            client_id=CLIENT_ID,
            name="Mystery Runner",
            slug="mystery-runner",
            sku_root="MYST",
            status="active",
        )
        unpriced_variant = ProductVariantModel(
            variant_id=new_uuid(),
            client_id=CLIENT_ID,
            product_id=unpriced_product.product_id,
            title="41 / Grey",
            sku="MYST-41-GREY",
            barcode="BC-MYST-41-GREY",
            option_values_json={"size": "41", "color": "Grey", "other": ""},
            status="active",
            reorder_level=Decimal("1"),
        )
        session.add_all([unpriced_product, unpriced_variant])
        session.flush()
        session.add(
            InventoryLedgerModel(
                entry_id=new_uuid(),
                client_id=CLIENT_ID,
                variant_id=unpriced_variant.variant_id,
                location_id=LOCATION_ID,
                movement_type="stock_received",
                reference_type="seed",
                reference_id=new_uuid(),
                reference_line_id=None,
                quantity_delta=Decimal("3"),
                unit_cost_amount=Decimal("25"),
                unit_price_amount=None,
                reason="Seed stock",
                created_by_user_id=USER_ID,
            )
        )
        session.commit()

    client = _login_client(runtime)

    search_response = client.get("/sales/variants/search", params={"q": "Runner"})
    assert search_response.status_code == 200
    search_items = search_response.json()["items"]
    assert len(search_items) == 1
    assert search_items[0]["variant_id"] == priced["variant_id"]
    assert Decimal(search_items[0]["unit_price"]) == Decimal("75")
    assert Decimal(search_items[0]["min_price"]) == Decimal("65")

    below_min_response = client.post(
        "/sales/orders",
        json={
            "customer": {
                "name": "Walker Min",
                "phone": "+971559999999",
                "email": "walker-min@example.com",
            },
            "lines": [
                {
                    "variant_id": priced["variant_id"],
                    "quantity": "1",
                    "unit_price": "75",
                    "discount_amount": "11",
                }
            ],
            "action": "confirm",
        },
    )
    assert below_min_response.status_code == 400
    assert below_min_response.json()["error"]["code"] == "MIN_PRICE_VIOLATION"
