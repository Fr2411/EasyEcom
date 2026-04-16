from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from easy_ecom.core.ids import new_uuid
from easy_ecom.data.store.postgres_models import (
    CategoryModel,
    ClientSettingsModel,
    InventoryLedgerModel,
    LocationModel,
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
USER_ID = "11111111-1111-1111-1111-111111111111"


def _seed_dependencies(tmp_path: Path):
    runtime = build_sqlite_runtime(tmp_path, "constraints.db")
    seed_auth_user(runtime.session_factory, user_id=USER_ID, client_id=CLIENT_ID, role_code="CLIENT_OWNER")

    with runtime.session_factory() as session:
        location_id = new_uuid()
        supplier_id = new_uuid()
        category_id = new_uuid()
        product_id = new_uuid()
        variant_id = new_uuid()
        purchase_id = new_uuid()
        order_id = new_uuid()
        return_id = new_uuid()

        session.add(
            ClientSettingsModel(
                client_settings_id=new_uuid(),
                client_id=CLIENT_ID,
                low_stock_threshold=Decimal("2"),
                allow_backorder=False,
                default_location_name="Main",
                require_discount_approval=False,
                order_prefix="SO",
                purchase_prefix="PO",
                return_prefix="RT",
            )
        )
        session.add(
            LocationModel(
                location_id=location_id,
                client_id=CLIENT_ID,
                name="Main",
                code="MAIN",
                is_default=True,
                status="active",
            )
        )
        session.add(
            SupplierModel(
                supplier_id=supplier_id,
                client_id=CLIENT_ID,
                name="Supplier",
                code="SUP-1",
                status="active",
            )
        )
        session.add(
            CategoryModel(
                category_id=category_id,
                client_id=CLIENT_ID,
                name="Category",
                slug="category",
                status="active",
            )
        )
        session.add(
            ProductModel(
                product_id=product_id,
                client_id=CLIENT_ID,
                category_id=category_id,
                supplier_id=supplier_id,
                name="Running Shoe",
                slug="running-shoe",
                status="active",
                default_price_amount=Decimal("100"),
                min_price_amount=Decimal("80"),
                max_discount_percent=Decimal("20"),
            )
        )
        session.add(
            ProductVariantModel(
                variant_id=variant_id,
                client_id=CLIENT_ID,
                product_id=product_id,
                title="M / Blue",
                sku="SHOE-M-BLUE",
                status="active",
                cost_amount=Decimal("50"),
                price_amount=Decimal("100"),
                min_price_amount=Decimal("80"),
                reorder_level=Decimal("1"),
            )
        )
        session.add(
            PurchaseModel(
                purchase_id=purchase_id,
                client_id=CLIENT_ID,
                supplier_id=supplier_id,
                location_id=location_id,
                purchase_number="PO-001",
                status="draft",
                created_by_user_id=USER_ID,
                subtotal_amount=Decimal("0"),
                total_amount=Decimal("0"),
            )
        )
        session.add(
            SalesOrderModel(
                sales_order_id=order_id,
                client_id=CLIENT_ID,
                location_id=location_id,
                order_number="SO-001",
                status="draft",
                created_by_user_id=USER_ID,
                subtotal_amount=Decimal("0"),
                discount_amount=Decimal("0"),
                total_amount=Decimal("0"),
                paid_amount=Decimal("0"),
            )
        )
        session.add(
            SalesReturnModel(
                sales_return_id=return_id,
                client_id=CLIENT_ID,
                return_number="RT-001",
                status="pending",
                refund_status="pending",
                created_by_user_id=USER_ID,
                subtotal_amount=Decimal("0"),
                refund_amount=Decimal("0"),
            )
        )
        session.commit()

    return runtime, {
        "location_id": location_id,
        "variant_id": variant_id,
        "purchase_id": purchase_id,
        "order_id": order_id,
        "return_id": return_id,
    }


def test_allows_valid_inventory_and_pricing_rows(tmp_path: Path) -> None:
    runtime, ids = _seed_dependencies(tmp_path)
    with runtime.session_factory() as session:
        session.add(
            PurchaseItemModel(
                purchase_item_id=new_uuid(),
                client_id=CLIENT_ID,
                purchase_id=ids["purchase_id"],
                variant_id=ids["variant_id"],
                quantity=Decimal("2"),
                received_quantity=Decimal("1"),
                unit_cost_amount=Decimal("50"),
                line_total_amount=Decimal("100"),
            )
        )
        session.add(
            InventoryLedgerModel(
                entry_id=new_uuid(),
                client_id=CLIENT_ID,
                variant_id=ids["variant_id"],
                location_id=ids["location_id"],
                movement_type="stock_received",
                reference_type="test",
                reference_id="ok",
                quantity_delta=Decimal("2"),
                unit_cost_amount=Decimal("50"),
                unit_price_amount=Decimal("100"),
                reason="seed",
                created_by_user_id=USER_ID,
            )
        )
        session.add(
            SalesOrderItemModel(
                sales_order_item_id=new_uuid(),
                client_id=CLIENT_ID,
                sales_order_id=ids["order_id"],
                variant_id=ids["variant_id"],
                quantity=Decimal("2"),
                quantity_fulfilled=Decimal("1"),
                quantity_cancelled=Decimal("0"),
                unit_price_amount=Decimal("100"),
                discount_amount=Decimal("5"),
                line_total_amount=Decimal("195"),
            )
        )
        session.add(
            SalesReturnItemModel(
                sales_return_item_id=new_uuid(),
                client_id=CLIENT_ID,
                sales_return_id=ids["return_id"],
                variant_id=ids["variant_id"],
                quantity=Decimal("1"),
                restock_quantity=Decimal("1"),
                unit_refund_amount=Decimal("100"),
                disposition="restock",
            )
        )
        session.commit()


def test_blocks_invalid_product_and_variant_pricing(tmp_path: Path) -> None:
    runtime, _ids = _seed_dependencies(tmp_path)

    with runtime.session_factory() as session:
        with pytest.raises(IntegrityError):
            session.add(
                ProductModel(
                    product_id=new_uuid(),
                    client_id=CLIENT_ID,
                    name="Bad Product",
                    slug="bad-product",
                    status="active",
                    default_price_amount=Decimal("10"),
                    min_price_amount=Decimal("20"),
                    max_discount_percent=Decimal("10"),
                )
            )
            session.commit()
        session.rollback()

        existing_product_id = session.execute(select(ProductModel.product_id)).scalar_one()
        with pytest.raises(IntegrityError):
            session.add(
                ProductVariantModel(
                    variant_id=new_uuid(),
                    client_id=CLIENT_ID,
                    product_id=existing_product_id,
                    title="Bad Variant",
                    sku="BAD-SKU-1",
                    status="active",
                    cost_amount=Decimal("10"),
                    price_amount=Decimal("20"),
                    min_price_amount=Decimal("25"),
                    reorder_level=Decimal("1"),
                )
            )
            session.commit()


def test_blocks_invalid_inventory_movement_and_sales_quantities(tmp_path: Path) -> None:
    runtime, ids = _seed_dependencies(tmp_path)

    with runtime.session_factory() as session:
        with pytest.raises(IntegrityError):
            session.add(
                InventoryLedgerModel(
                    entry_id=new_uuid(),
                    client_id=CLIENT_ID,
                    variant_id=ids["variant_id"],
                    location_id=ids["location_id"],
                    movement_type="adjustment",
                    reference_type="test",
                    reference_id="zero",
                    quantity_delta=Decimal("0"),
                    reason="invalid",
                    created_by_user_id=USER_ID,
                )
            )
            session.commit()
        session.rollback()

        with pytest.raises(IntegrityError):
            session.add(
                SalesOrderItemModel(
                    sales_order_item_id=new_uuid(),
                    client_id=CLIENT_ID,
                    sales_order_id=ids["order_id"],
                    variant_id=ids["variant_id"],
                    quantity=Decimal("1"),
                    quantity_fulfilled=Decimal("1"),
                    quantity_cancelled=Decimal("1"),
                    unit_price_amount=Decimal("100"),
                    discount_amount=Decimal("0"),
                    line_total_amount=Decimal("100"),
                )
            )
            session.commit()
        session.rollback()

        with pytest.raises(IntegrityError):
            session.add(
                SalesReturnItemModel(
                    sales_return_item_id=new_uuid(),
                    client_id=CLIENT_ID,
                    sales_return_id=ids["return_id"],
                    variant_id=ids["variant_id"],
                    quantity=Decimal("1"),
                    restock_quantity=Decimal("2"),
                    unit_refund_amount=Decimal("50"),
                    disposition="restock",
                )
            )
            session.commit()
