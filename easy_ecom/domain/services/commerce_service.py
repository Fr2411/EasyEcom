from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session, sessionmaker

from easy_ecom.core.errors import ApiException
from easy_ecom.core.ids import new_uuid
from easy_ecom.core.slugs import slugify_identifier
from easy_ecom.core.time_utils import now_utc
from easy_ecom.data.store.postgres_models import (
    CategoryModel,
    ClientSettingsModel,
    CustomerModel,
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
    ShipmentModel,
    SupplierModel,
)
from easy_ecom.domain.models.auth import AuthenticatedUser


ZERO = Decimal("0")


def normalize_email(value: str) -> str:
    return value.strip().lower()


def normalize_phone(value: str) -> str:
    return "".join(char for char in value if char.isdigit())


def as_decimal(value: Any) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if value is None:
        return ZERO
    return Decimal(str(value))


def option_value(options: dict[str, Any] | None, key: str) -> str:
    if not options:
        return ""
    value = options.get(key)
    return str(value).strip() if value is not None else ""


def build_variant_title(*parts: str) -> str:
    normalized = [part.strip() for part in parts if str(part).strip()]
    return " / ".join(normalized) if normalized else "Default"


def build_variant_label(product_name: str, title: str) -> str:
    clean_title = title.strip() or "Default"
    return f"{product_name.strip()} / {clean_title}"


def build_product_slug(name: str) -> str:
    return slugify_identifier(name, max_length=128, default="product")


def _new_number(prefix: str) -> str:
    stamp = now_utc().strftime("%Y%m%d%H%M%S")
    return f"{prefix}-{stamp}-{new_uuid()[:4].upper()}"


def _require(condition: bool, *, message: str, code: str = "INVALID_REQUEST", status_code: int = 400) -> None:
    if not condition:
        raise ApiException(status_code=status_code, code=code, message=message)


def _require_page(user: AuthenticatedUser, page: str) -> None:
    if page not in user.allowed_pages and "SUPER_ADMIN" not in user.roles:
        raise ApiException(status_code=403, code="ACCESS_DENIED", message=f"Access denied for {page}")


@dataclass(frozen=True)
class LocationContext:
    active_location_id: str
    active_location_name: str
    has_multiple_locations: bool
    locations: list[LocationModel]


class CommerceBaseService:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def _active_locations(self, session: Session, client_id: str) -> list[LocationModel]:
        return list(
            session.execute(
                select(LocationModel)
                .where(LocationModel.client_id == client_id, LocationModel.status == "active")
                .order_by(LocationModel.is_default.desc(), LocationModel.name.asc())
            ).scalars()
        )

    def _location_context(
        self,
        session: Session,
        client_id: str,
        requested_location_id: str | None = None,
    ) -> LocationContext:
        locations = self._active_locations(session, client_id)
        _require(bool(locations), message="No active location is configured for this tenant", code="LOCATION_REQUIRED")
        chosen = None
        if requested_location_id:
            for location in locations:
                if str(location.location_id) == requested_location_id:
                    chosen = location
                    break
            _require(chosen is not None, message="Requested location was not found", code="LOCATION_NOT_FOUND", status_code=404)
        else:
            chosen = next((item for item in locations if item.is_default), locations[0])
        return LocationContext(
            active_location_id=str(chosen.location_id),
            active_location_name=chosen.name,
            has_multiple_locations=len(locations) > 1,
            locations=locations,
        )

    def _client_settings(self, session: Session, client_id: str) -> ClientSettingsModel | None:
        return session.execute(
            select(ClientSettingsModel).where(ClientSettingsModel.client_id == client_id)
        ).scalar_one_or_none()

    def _stock_maps(
        self,
        session: Session,
        client_id: str,
        location_id: str,
    ) -> tuple[dict[str, Decimal], dict[str, Decimal]]:
        on_hand = {
            str(variant_id): as_decimal(quantity)
            for variant_id, quantity in session.execute(
                select(
                    InventoryLedgerModel.variant_id,
                    func.coalesce(func.sum(InventoryLedgerModel.quantity_delta), ZERO),
                )
                .where(
                    InventoryLedgerModel.client_id == client_id,
                    InventoryLedgerModel.location_id == location_id,
                )
                .group_by(InventoryLedgerModel.variant_id)
            ).all()
        }

        reserved = {
            str(variant_id): as_decimal(quantity)
            for variant_id, quantity in session.execute(
                select(
                    SalesOrderItemModel.variant_id,
                    func.coalesce(
                        func.sum(
                            SalesOrderItemModel.quantity
                            - SalesOrderItemModel.quantity_fulfilled
                            - SalesOrderItemModel.quantity_cancelled
                        ),
                        ZERO,
                    ),
                )
                .join(SalesOrderModel, SalesOrderModel.sales_order_id == SalesOrderItemModel.sales_order_id)
                .where(
                    SalesOrderItemModel.client_id == client_id,
                    SalesOrderModel.client_id == client_id,
                    SalesOrderModel.location_id == location_id,
                    SalesOrderModel.status == "confirmed",
                )
                .group_by(SalesOrderItemModel.variant_id)
            ).all()
        }
        return on_hand, reserved

    def _base_variant_stmt(self, client_id: str) -> Select[tuple[ProductModel, ProductVariantModel, SupplierModel | None, CategoryModel | None]]:
        return (
            select(ProductModel, ProductVariantModel, SupplierModel, CategoryModel)
            .join(ProductVariantModel, ProductVariantModel.product_id == ProductModel.product_id)
            .outerjoin(SupplierModel, SupplierModel.supplier_id == ProductModel.supplier_id)
            .outerjoin(CategoryModel, CategoryModel.category_id == ProductModel.category_id)
            .where(
                ProductModel.client_id == client_id,
                ProductVariantModel.client_id == client_id,
            )
            .order_by(ProductModel.name.asc(), ProductVariantModel.title.asc())
        )

    def _apply_variant_search(self, stmt: Select[Any], query: str) -> Select[Any]:
        trimmed = query.strip().lower()
        if not trimmed:
            return stmt
        pattern = f"%{trimmed}%"
        return stmt.where(
            or_(
                func.lower(ProductModel.name).like(pattern),
                func.lower(ProductVariantModel.title).like(pattern),
                func.lower(ProductVariantModel.sku).like(pattern),
                func.lower(ProductVariantModel.barcode).like(pattern),
            )
        )

    def _serialize_locations(self, context: LocationContext) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        locations = [
            {
                "location_id": str(location.location_id),
                "name": location.name,
                "is_default": bool(location.is_default),
            }
            for location in context.locations
        ]
        active = next(item for item in locations if item["location_id"] == context.active_location_id)
        return locations, active

    def _ensure_category(self, session: Session, client_id: str, name: str) -> str | None:
        trimmed = name.strip()
        if not trimmed:
            return None
        slug = slugify_identifier(trimmed, max_length=128, default="category")
        existing = session.execute(
            select(CategoryModel).where(CategoryModel.client_id == client_id, CategoryModel.slug == slug)
        ).scalar_one_or_none()
        if existing:
            if existing.name != trimmed:
                existing.name = trimmed
            return str(existing.category_id)
        category = CategoryModel(
            category_id=new_uuid(),
            client_id=client_id,
            name=trimmed,
            slug=slug,
            status="active",
        )
        session.add(category)
        session.flush()
        return str(category.category_id)

    def _ensure_supplier(self, session: Session, client_id: str, name: str) -> str | None:
        trimmed = name.strip()
        if not trimmed:
            return None
        normalized = slugify_identifier(trimmed, max_length=64, default="supplier")
        existing = session.execute(
            select(SupplierModel).where(SupplierModel.client_id == client_id, SupplierModel.code == normalized)
        ).scalar_one_or_none()
        if existing:
            if existing.name != trimmed:
                existing.name = trimmed
            return str(existing.supplier_id)
        supplier = SupplierModel(
            supplier_id=new_uuid(),
            client_id=client_id,
            name=trimmed,
            code=normalized,
            status="active",
        )
        session.add(supplier)
        session.flush()
        return str(supplier.supplier_id)

    def _variant_payload(self, product: ProductModel, variant: ProductVariantModel, on_hand: Decimal, reserved: Decimal) -> dict[str, Any]:
        size = option_value(variant.option_values_json, "size")
        color = option_value(variant.option_values_json, "color")
        other = option_value(variant.option_values_json, "other")
        return {
            "variant_id": str(variant.variant_id),
            "product_id": str(product.product_id),
            "product_name": product.name,
            "title": variant.title,
            "label": build_variant_label(product.name, variant.title),
            "sku": variant.sku,
            "barcode": variant.barcode,
            "status": variant.status,
            "options": {
                "size": size,
                "color": color,
                "other": other,
            },
            "unit_cost": as_decimal(variant.cost_amount),
            "unit_price": as_decimal(variant.price_amount),
            "min_price": as_decimal(variant.min_price_amount),
            "reorder_level": as_decimal(variant.reorder_level),
            "on_hand": on_hand,
            "reserved": reserved,
            "available_to_sell": on_hand - reserved,
        }

    def _sales_order_payload(self, session: Session, order: SalesOrderModel) -> dict[str, Any]:
        customer = None
        if order.customer_id:
            customer = session.execute(
                select(CustomerModel).where(
                    CustomerModel.client_id == order.client_id,
                    CustomerModel.customer_id == order.customer_id,
                )
            ).scalar_one_or_none()
        location = session.execute(
            select(LocationModel).where(LocationModel.location_id == order.location_id)
        ).scalar_one()
        line_rows = session.execute(
            select(SalesOrderItemModel, ProductVariantModel, ProductModel)
            .join(ProductVariantModel, ProductVariantModel.variant_id == SalesOrderItemModel.variant_id)
            .join(ProductModel, ProductModel.product_id == ProductVariantModel.product_id)
            .where(
                SalesOrderItemModel.client_id == order.client_id,
                SalesOrderItemModel.sales_order_id == order.sales_order_id,
            )
            .order_by(SalesOrderItemModel.created_at.asc())
        ).all()
        lines = []
        for item, variant, product in line_rows:
            reserved_quantity = max(
                ZERO,
                as_decimal(item.quantity) - as_decimal(item.quantity_fulfilled) - as_decimal(item.quantity_cancelled),
            )
            lines.append(
                {
                    "sales_order_item_id": str(item.sales_order_item_id),
                    "variant_id": str(variant.variant_id),
                    "product_id": str(product.product_id),
                    "product_name": product.name,
                    "label": build_variant_label(product.name, variant.title),
                    "sku": variant.sku,
                    "quantity": as_decimal(item.quantity),
                    "quantity_fulfilled": as_decimal(item.quantity_fulfilled),
                    "quantity_cancelled": as_decimal(item.quantity_cancelled),
                    "reserved_quantity": reserved_quantity if order.status == "confirmed" else ZERO,
                    "unit_price": as_decimal(item.unit_price_amount),
                    "discount_amount": as_decimal(item.discount_amount),
                    "line_total": as_decimal(item.line_total_amount),
                }
            )
        return {
            "sales_order_id": str(order.sales_order_id),
            "order_number": order.order_number,
            "customer_id": str(order.customer_id) if order.customer_id else None,
            "customer_name": customer.name if customer else "",
            "customer_phone": customer.phone if customer else "",
            "customer_email": customer.email if customer else "",
            "location_id": str(location.location_id),
            "location_name": location.name,
            "status": order.status,
            "payment_status": order.payment_status,
            "shipment_status": order.shipment_status,
            "ordered_at": order.ordered_at.isoformat() if order.ordered_at else None,
            "confirmed_at": order.confirmed_at.isoformat() if order.confirmed_at else None,
            "notes": order.notes,
            "subtotal_amount": as_decimal(order.subtotal_amount),
            "discount_amount": as_decimal(order.discount_amount),
            "total_amount": as_decimal(order.total_amount),
            "paid_amount": as_decimal(order.paid_amount),
            "lines": lines,
        }

    def _return_payload(self, session: Session, record: SalesReturnModel) -> dict[str, Any]:
        order = None
        if record.sales_order_id:
            order = session.execute(
                select(SalesOrderModel).where(
                    SalesOrderModel.client_id == record.client_id,
                    SalesOrderModel.sales_order_id == record.sales_order_id,
                )
            ).scalar_one_or_none()
        customer = None
        if record.customer_id:
            customer = session.execute(
                select(CustomerModel).where(
                    CustomerModel.client_id == record.client_id,
                    CustomerModel.customer_id == record.customer_id,
                )
            ).scalar_one_or_none()
        line_rows = session.execute(
            select(SalesReturnItemModel, ProductVariantModel, ProductModel)
            .join(ProductVariantModel, ProductVariantModel.variant_id == SalesReturnItemModel.variant_id)
            .join(ProductModel, ProductModel.product_id == ProductVariantModel.product_id)
            .where(
                SalesReturnItemModel.client_id == record.client_id,
                SalesReturnItemModel.sales_return_id == record.sales_return_id,
            )
            .order_by(SalesReturnItemModel.created_at.asc())
        ).all()
        lines = []
        for item, variant, product in line_rows:
            quantity = as_decimal(item.quantity)
            unit_refund_amount = as_decimal(item.unit_refund_amount)
            lines.append(
                {
                    "sales_return_item_id": str(item.sales_return_item_id),
                    "sales_order_item_id": str(item.sales_order_item_id) if item.sales_order_item_id else None,
                    "variant_id": str(variant.variant_id),
                    "product_name": product.name,
                    "label": build_variant_label(product.name, variant.title),
                    "quantity": quantity,
                    "restock_quantity": as_decimal(item.restock_quantity),
                    "disposition": item.disposition,
                    "unit_refund_amount": unit_refund_amount,
                    "line_total": quantity * unit_refund_amount,
                }
            )
        return {
            "sales_return_id": str(record.sales_return_id),
            "return_number": record.return_number,
            "sales_order_id": str(record.sales_order_id) if record.sales_order_id else None,
            "order_number": order.order_number if order else "",
            "customer_name": customer.name if customer else "",
            "customer_phone": customer.phone if customer else "",
            "status": record.status,
            "refund_status": record.refund_status,
            "notes": record.notes,
            "subtotal_amount": as_decimal(record.subtotal_amount),
            "refund_amount": as_decimal(record.refund_amount),
            "requested_at": record.requested_at.isoformat() if record.requested_at else None,
            "received_at": record.received_at.isoformat() if record.received_at else None,
            "lines": lines,
        }


class CatalogService(CommerceBaseService):
    def _product_payload(
        self,
        session: Session,
        client_id: str,
        product_id: str,
        location_id: str,
    ) -> dict[str, Any]:
        on_hand_map, reserved_map = self._stock_maps(session, client_id, location_id)
        rows = session.execute(
            self._base_variant_stmt(client_id).where(ProductModel.product_id == product_id)
        ).all()
        _require(bool(rows), message="Product not found", code="PRODUCT_NOT_FOUND", status_code=404)
        product, _variant, supplier, category = rows[0]
        payload = {
            "product_id": str(product.product_id),
            "name": product.name,
            "brand": product.brand,
            "status": product.status,
            "supplier": supplier.name if supplier else "",
            "category": category.name if category else "",
            "description": product.description,
            "sku_root": product.sku_root,
            "default_price": as_decimal(product.default_price_amount),
            "min_price": as_decimal(product.min_price_amount),
            "max_discount_percent": as_decimal(product.max_discount_percent),
            "variants": [],
        }
        for _product, variant, _supplier, _category in rows:
            payload["variants"].append(
                self._variant_payload(
                    product,
                    variant,
                    on_hand_map.get(str(variant.variant_id), ZERO),
                    reserved_map.get(str(variant.variant_id), ZERO),
                )
            )
        return payload

    def workspace(
        self,
        user: AuthenticatedUser,
        *,
        query: str = "",
        location_id: str | None = None,
        include_oos: bool = False,
    ) -> dict[str, Any]:
        _require_page(user, "Catalog")
        with self._session_factory() as session:
            location_context = self._location_context(session, user.client_id, location_id)
            on_hand_map, reserved_map = self._stock_maps(session, user.client_id, location_context.active_location_id)
            stmt = self._apply_variant_search(self._base_variant_stmt(user.client_id), query)
            rows = session.execute(stmt).all()

            products: dict[str, dict[str, Any]] = {}
            for product, variant, supplier, category in rows:
                on_hand = on_hand_map.get(str(variant.variant_id), ZERO)
                reserved = reserved_map.get(str(variant.variant_id), ZERO)
                available = on_hand - reserved
                if product.status != "active" or variant.status != "active":
                    continue
                if not include_oos and available <= ZERO:
                    continue
                product_key = str(product.product_id)
                if product_key not in products:
                    products[product_key] = {
                        "product_id": product_key,
                        "name": product.name,
                        "brand": product.brand,
                        "status": product.status,
                        "supplier": supplier.name if supplier else "",
                        "category": category.name if category else "",
                        "description": product.description,
                        "sku_root": product.sku_root,
                        "default_price": as_decimal(product.default_price_amount),
                        "min_price": as_decimal(product.min_price_amount),
                        "max_discount_percent": as_decimal(product.max_discount_percent),
                        "variants": [],
                    }
                products[product_key]["variants"].append(
                    self._variant_payload(product, variant, on_hand, reserved)
                )

            categories = [
                {"category_id": str(record.category_id), "name": record.name}
                for record in session.execute(
                    select(CategoryModel)
                    .where(CategoryModel.client_id == user.client_id, CategoryModel.status == "active")
                    .order_by(CategoryModel.name.asc())
                ).scalars()
            ]
            suppliers = [
                {"supplier_id": str(record.supplier_id), "name": record.name}
                for record in session.execute(
                    select(SupplierModel)
                    .where(SupplierModel.client_id == user.client_id, SupplierModel.status == "active")
                    .order_by(SupplierModel.name.asc())
                ).scalars()
            ]
            locations, active = self._serialize_locations(location_context)
            return {
                "query": query,
                "has_multiple_locations": location_context.has_multiple_locations,
                "active_location": active,
                "locations": locations,
                "categories": categories,
                "suppliers": suppliers,
                "items": list(products.values()),
            }

    def upsert_product(
        self,
        user: AuthenticatedUser,
        *,
        product_id: str | None,
        identity: dict[str, Any],
        variants: list[dict[str, Any]],
    ) -> dict[str, Any]:
        _require_page(user, "Catalog")
        _require(bool(variants), message="At least one variant is required")
        with self._session_factory() as session:
            supplier_id = self._ensure_supplier(session, user.client_id, str(identity.get("supplier", "")))
            category_id = self._ensure_category(session, user.client_id, str(identity.get("category", "")))

            product = None
            if product_id:
                product = session.execute(
                    select(ProductModel).where(
                        ProductModel.client_id == user.client_id,
                        ProductModel.product_id == product_id,
                    )
                ).scalar_one_or_none()
                _require(product is not None, message="Product not found", code="PRODUCT_NOT_FOUND", status_code=404)
            else:
                product = ProductModel(
                    product_id=new_uuid(),
                    client_id=user.client_id,
                    slug=build_product_slug(str(identity["product_name"])),
                )
                session.add(product)

            product.category_id = category_id
            product.supplier_id = supplier_id
            product.name = str(identity["product_name"]).strip()
            product.slug = build_product_slug(product.name)
            product.sku_root = str(identity.get("sku_root", "")).strip()
            product.brand = str(identity.get("brand", "")).strip()
            product.description = str(identity.get("description", "")).strip()
            product.image_url = str(identity.get("image_url", "")).strip()
            product.status = str(identity.get("status", "active")).strip() or "active"
            product.default_price_amount = as_decimal(identity.get("default_selling_price"))
            product.min_price_amount = as_decimal(identity.get("min_selling_price"))
            product.max_discount_percent = as_decimal(identity.get("max_discount_percent"))
            session.flush()

            for variant_payload in variants:
                sku = str(variant_payload["sku"]).strip()
                _require(bool(sku), message="Variant SKU is required")
                existing = session.execute(
                    select(ProductVariantModel).where(
                        ProductVariantModel.client_id == user.client_id,
                        ProductVariantModel.sku == sku,
                    )
                ).scalar_one_or_none()
                requested_variant_id = variant_payload.get("variant_id")
                if requested_variant_id:
                    variant = session.execute(
                        select(ProductVariantModel).where(
                            ProductVariantModel.client_id == user.client_id,
                            ProductVariantModel.variant_id == requested_variant_id,
                        )
                    ).scalar_one_or_none()
                    _require(variant is not None, message="Variant not found", code="VARIANT_NOT_FOUND", status_code=404)
                else:
                    variant = existing if existing and str(existing.product_id) == str(product.product_id) else None
                    if variant is None:
                        variant = ProductVariantModel(
                            variant_id=new_uuid(),
                            client_id=user.client_id,
                            product_id=product.product_id,
                        )
                        session.add(variant)
                if existing is not None and str(existing.variant_id) != str(variant.variant_id):
                    raise ApiException(status_code=400, code="DUPLICATE_SKU", message="Variant SKU already exists")
                size = str(variant_payload.get("size", "")).strip()
                color = str(variant_payload.get("color", "")).strip()
                other = str(variant_payload.get("other", "")).strip()
                variant.product_id = product.product_id
                variant.title = build_variant_title(size, color, other)
                variant.sku = sku
                variant.barcode = str(variant_payload.get("barcode", "")).strip()
                variant.option_values_json = {"size": size, "color": color, "other": other}
                variant.status = str(variant_payload.get("status", "active")).strip() or "active"
                variant.cost_amount = as_decimal(variant_payload.get("default_purchase_price"))
                variant.price_amount = as_decimal(variant_payload.get("default_selling_price"))
                variant.min_price_amount = as_decimal(variant_payload.get("min_selling_price"))
                variant.reorder_level = as_decimal(variant_payload.get("reorder_level"))

            session.commit()
            location_context = self._location_context(session, user.client_id)
            return self._product_payload(
                session,
                user.client_id,
                str(product.product_id),
                location_context.active_location_id,
            )


class InventoryService(CommerceBaseService):
    def workspace(self, user: AuthenticatedUser, *, query: str = "", location_id: str | None = None) -> dict[str, Any]:
        _require_page(user, "Inventory")
        with self._session_factory() as session:
            location_context = self._location_context(session, user.client_id, location_id)
            settings = self._client_settings(session, user.client_id)
            default_threshold = as_decimal(settings.low_stock_threshold) if settings else ZERO
            on_hand_map, reserved_map = self._stock_maps(session, user.client_id, location_context.active_location_id)
            rows = session.execute(self._apply_variant_search(self._base_variant_stmt(user.client_id), query)).all()
            stock_items = []
            low_stock = []
            for product, variant, supplier, category in rows:
                if product.status != "active" or variant.status != "active":
                    continue
                on_hand = on_hand_map.get(str(variant.variant_id), ZERO)
                reserved = reserved_map.get(str(variant.variant_id), ZERO)
                available = on_hand - reserved
                if available <= ZERO:
                    continue
                threshold = as_decimal(variant.reorder_level) if as_decimal(variant.reorder_level) > ZERO else default_threshold
                row = {
                    "variant_id": str(variant.variant_id),
                    "product_id": str(product.product_id),
                    "product_name": product.name,
                    "label": build_variant_label(product.name, variant.title),
                    "sku": variant.sku,
                    "barcode": variant.barcode,
                    "supplier": supplier.name if supplier else "",
                    "category": category.name if category else "",
                    "location_id": location_context.active_location_id,
                    "location_name": location_context.active_location_name,
                    "unit_cost": as_decimal(variant.cost_amount),
                    "unit_price": as_decimal(variant.price_amount),
                    "reorder_level": as_decimal(variant.reorder_level),
                    "on_hand": on_hand,
                    "reserved": reserved,
                    "available_to_sell": available,
                    "low_stock": threshold > ZERO and available <= threshold,
                }
                stock_items.append(row)
                if row["low_stock"]:
                    low_stock.append(row)
            locations, active = self._serialize_locations(location_context)
            return {
                "query": query,
                "has_multiple_locations": location_context.has_multiple_locations,
                "active_location": active,
                "locations": locations,
                "stock_items": stock_items,
                "low_stock_items": low_stock,
            }

    def receive_stock(
        self,
        user: AuthenticatedUser,
        *,
        location_id: str | None,
        quantity: Decimal,
        notes: str,
        identity: dict[str, Any],
        variant_payload: dict[str, Any],
    ) -> dict[str, Any]:
        _require_page(user, "Inventory")
        with self._session_factory() as session:
            location_context = self._location_context(session, user.client_id, location_id)
            supplier_id = self._ensure_supplier(session, user.client_id, str(identity.get("supplier", "")))
            category_id = self._ensure_category(session, user.client_id, str(identity.get("category", "")))

            product = None
            requested_product_id = identity.get("product_id")
            requested_variant_id = variant_payload.get("variant_id")

            if requested_product_id:
                product = session.execute(
                    select(ProductModel).where(
                        ProductModel.client_id == user.client_id,
                        ProductModel.product_id == requested_product_id,
                    )
                ).scalar_one_or_none()

            if product is None:
                sku_root = str(identity.get("sku_root", "")).strip()
                if requested_variant_id:
                    variant = session.execute(
                        select(ProductVariantModel).where(
                            ProductVariantModel.client_id == user.client_id,
                            ProductVariantModel.variant_id == requested_variant_id,
                        )
                    ).scalar_one_or_none()
                    _require(variant is not None, message="Variant not found", code="VARIANT_NOT_FOUND", status_code=404)
                    product = session.execute(
                        select(ProductModel).where(
                            ProductModel.client_id == user.client_id,
                            ProductModel.product_id == variant.product_id,
                        )
                    ).scalar_one()
                elif sku_root:
                    product = session.execute(
                        select(ProductModel).where(
                            ProductModel.client_id == user.client_id,
                            ProductModel.sku_root == sku_root,
                        )
                    ).scalar_one_or_none()

            if product is None:
                product = ProductModel(
                    product_id=new_uuid(),
                    client_id=user.client_id,
                    slug=build_product_slug(str(identity["product_name"])),
                )
                session.add(product)

            product.category_id = category_id
            product.supplier_id = supplier_id
            product.name = str(identity["product_name"]).strip()
            product.slug = build_product_slug(product.name)
            product.sku_root = str(identity.get("sku_root", "")).strip()
            product.brand = str(identity.get("brand", "")).strip()
            product.description = str(identity.get("description", "")).strip()
            product.image_url = str(identity.get("image_url", "")).strip()
            product.status = "active"
            product.default_price_amount = as_decimal(identity.get("default_selling_price"))
            product.min_price_amount = as_decimal(identity.get("min_selling_price"))
            product.max_discount_percent = as_decimal(identity.get("max_discount_percent"))
            session.flush()

            variant = None
            if requested_variant_id:
                variant = session.execute(
                    select(ProductVariantModel).where(
                        ProductVariantModel.client_id == user.client_id,
                        ProductVariantModel.variant_id == requested_variant_id,
                    )
                ).scalar_one_or_none()
                _require(variant is not None, message="Variant not found", code="VARIANT_NOT_FOUND", status_code=404)
            else:
                sku = str(variant_payload["sku"]).strip()
                variant = session.execute(
                    select(ProductVariantModel).where(
                        ProductVariantModel.client_id == user.client_id,
                        ProductVariantModel.sku == sku,
                    )
                ).scalar_one_or_none()
                if variant is None:
                    variant = ProductVariantModel(
                        variant_id=new_uuid(),
                        client_id=user.client_id,
                        product_id=product.product_id,
                    )
                    session.add(variant)
                else:
                    _require(
                        str(variant.product_id) == str(product.product_id),
                        message="SKU already belongs to a different product",
                        code="DUPLICATE_SKU",
                    )

            size = str(variant_payload.get("size", "")).strip()
            color = str(variant_payload.get("color", "")).strip()
            other = str(variant_payload.get("other", "")).strip()
            variant.product_id = product.product_id
            variant.title = build_variant_title(size, color, other)
            variant.sku = str(variant_payload["sku"]).strip()
            variant.barcode = str(variant_payload.get("barcode", "")).strip()
            variant.option_values_json = {"size": size, "color": color, "other": other}
            variant.status = "active"
            variant.cost_amount = as_decimal(variant_payload.get("default_purchase_price"))
            variant.price_amount = as_decimal(variant_payload.get("default_selling_price"))
            variant.min_price_amount = as_decimal(variant_payload.get("min_selling_price"))
            variant.reorder_level = as_decimal(variant_payload.get("reorder_level"))
            session.flush()

            settings = self._client_settings(session, user.client_id)
            prefix = settings.purchase_prefix if settings else "PO"
            purchase = PurchaseModel(
                purchase_id=new_uuid(),
                client_id=user.client_id,
                supplier_id=supplier_id,
                location_id=location_context.active_location_id,
                purchase_number=_new_number(prefix),
                status="received",
                ordered_at=now_utc(),
                received_at=now_utc(),
                notes=notes.strip(),
                created_by_user_id=user.user_id,
                subtotal_amount=quantity * as_decimal(variant.cost_amount),
                total_amount=quantity * as_decimal(variant.cost_amount),
            )
            session.add(purchase)
            session.flush()

            purchase_item = PurchaseItemModel(
                purchase_item_id=new_uuid(),
                client_id=user.client_id,
                purchase_id=purchase.purchase_id,
                variant_id=variant.variant_id,
                quantity=quantity,
                received_quantity=quantity,
                unit_cost_amount=as_decimal(variant.cost_amount),
                line_total_amount=quantity * as_decimal(variant.cost_amount),
                notes=notes.strip(),
            )
            session.add(purchase_item)
            session.add(
                InventoryLedgerModel(
                    entry_id=new_uuid(),
                    client_id=user.client_id,
                    variant_id=variant.variant_id,
                    location_id=location_context.active_location_id,
                    movement_type="stock_received",
                    reference_type="purchase",
                    reference_id=str(purchase.purchase_id),
                    reference_line_id=str(purchase_item.purchase_item_id),
                    quantity_delta=quantity,
                    unit_cost_amount=as_decimal(variant.cost_amount),
                    unit_price_amount=as_decimal(variant.price_amount),
                    reason=notes.strip() or "Stock received",
                    created_by_user_id=user.user_id,
                )
            )
            session.commit()

            on_hand_map, reserved_map = self._stock_maps(session, user.client_id, location_context.active_location_id)
            product = session.execute(
                select(ProductModel).where(ProductModel.product_id == variant.product_id)
            ).scalar_one()
            return {
                "purchase_id": str(purchase.purchase_id),
                "purchase_number": purchase.purchase_number,
                "variant": self._variant_payload(
                    product,
                    variant,
                    on_hand_map.get(str(variant.variant_id), ZERO),
                    reserved_map.get(str(variant.variant_id), ZERO),
                ),
            }

    def adjust_stock(
        self,
        user: AuthenticatedUser,
        *,
        location_id: str | None,
        variant_id: str,
        quantity_delta: Decimal,
        reason: str,
        notes: str,
    ) -> dict[str, Any]:
        _require_page(user, "Inventory")
        _require(quantity_delta != ZERO, message="Adjustment quantity cannot be zero")
        with self._session_factory() as session:
            location_context = self._location_context(session, user.client_id, location_id)
            variant_row = session.execute(
                self._base_variant_stmt(user.client_id).where(ProductVariantModel.variant_id == variant_id)
            ).first()
            _require(variant_row is not None, message="Variant not found", code="VARIANT_NOT_FOUND", status_code=404)
            product, variant, supplier, category = variant_row
            on_hand_map, reserved_map = self._stock_maps(session, user.client_id, location_context.active_location_id)
            on_hand = on_hand_map.get(str(variant.variant_id), ZERO)
            reserved = reserved_map.get(str(variant.variant_id), ZERO)
            available = on_hand - reserved
            if quantity_delta < ZERO:
                _require(
                    available + quantity_delta >= ZERO,
                    message="Adjustment would take available stock below zero",
                    code="INSUFFICIENT_STOCK",
                )
            session.add(
                InventoryLedgerModel(
                    entry_id=new_uuid(),
                    client_id=user.client_id,
                    variant_id=variant.variant_id,
                    location_id=location_context.active_location_id,
                    movement_type="adjustment",
                    reference_type="adjustment",
                    reference_id=new_uuid(),
                    reference_line_id=None,
                    quantity_delta=quantity_delta,
                    unit_cost_amount=as_decimal(variant.cost_amount),
                    unit_price_amount=as_decimal(variant.price_amount),
                    reason=f"{reason.strip()}: {notes.strip()}".strip(": "),
                    created_by_user_id=user.user_id,
                )
            )
            session.commit()
            on_hand_map, reserved_map = self._stock_maps(session, user.client_id, location_context.active_location_id)
            threshold = as_decimal(variant.reorder_level)
            refreshed_on_hand = on_hand_map.get(str(variant.variant_id), ZERO)
            refreshed_reserved = reserved_map.get(str(variant.variant_id), ZERO)
            refreshed_available = refreshed_on_hand - refreshed_reserved
            return {
                "variant_id": str(variant.variant_id),
                "product_id": str(product.product_id),
                "product_name": product.name,
                "label": build_variant_label(product.name, variant.title),
                "sku": variant.sku,
                "barcode": variant.barcode,
                "supplier": supplier.name if supplier else "",
                "category": category.name if category else "",
                "location_id": location_context.active_location_id,
                "location_name": location_context.active_location_name,
                "unit_cost": as_decimal(variant.cost_amount),
                "unit_price": as_decimal(variant.price_amount),
                "reorder_level": threshold,
                "on_hand": refreshed_on_hand,
                "reserved": refreshed_reserved,
                "available_to_sell": refreshed_available,
                "low_stock": threshold > ZERO and refreshed_available <= threshold,
            }


class SalesService(CommerceBaseService):
    def list_orders(self, user: AuthenticatedUser, *, status: str | None = None, query: str = "") -> list[dict[str, Any]]:
        _require_page(user, "Sales")
        with self._session_factory() as session:
            stmt = select(SalesOrderModel).where(SalesOrderModel.client_id == user.client_id)
            if status:
                stmt = stmt.where(SalesOrderModel.status == status)
            trimmed = query.strip().lower()
            if trimmed:
                pattern = f"%{trimmed}%"
                stmt = (
                    stmt.outerjoin(CustomerModel, CustomerModel.customer_id == SalesOrderModel.customer_id)
                    .where(
                        or_(
                            func.lower(SalesOrderModel.order_number).like(pattern),
                            func.lower(CustomerModel.phone).like(pattern),
                            func.lower(CustomerModel.email).like(pattern),
                        )
                    )
                )
            stmt = stmt.order_by(SalesOrderModel.created_at.desc())
            orders = session.execute(stmt).scalars().all()
            return [self._sales_order_payload(session, order) for order in orders]

    def get_order(self, user: AuthenticatedUser, sales_order_id: str) -> dict[str, Any]:
        _require_page(user, "Sales")
        with self._session_factory() as session:
            order = session.execute(
                select(SalesOrderModel).where(
                    SalesOrderModel.client_id == user.client_id,
                    SalesOrderModel.sales_order_id == sales_order_id,
                )
            ).scalar_one_or_none()
            _require(order is not None, message="Order not found", code="ORDER_NOT_FOUND", status_code=404)
            return self._sales_order_payload(session, order)

    def lookup_variants(self, user: AuthenticatedUser, *, query: str, location_id: str | None = None) -> list[dict[str, Any]]:
        _require_page(user, "Sales")
        with self._session_factory() as session:
            location_context = self._location_context(session, user.client_id, location_id)
            on_hand_map, reserved_map = self._stock_maps(session, user.client_id, location_context.active_location_id)
            rows = session.execute(self._apply_variant_search(self._base_variant_stmt(user.client_id), query)).all()
            items = []
            for product, variant, _supplier, _category in rows:
                if product.status != "active" or variant.status != "active":
                    continue
                available = on_hand_map.get(str(variant.variant_id), ZERO) - reserved_map.get(str(variant.variant_id), ZERO)
                if available <= ZERO:
                    continue
                items.append(
                    {
                        "variant_id": str(variant.variant_id),
                        "product_id": str(product.product_id),
                        "product_name": product.name,
                        "label": build_variant_label(product.name, variant.title),
                        "sku": variant.sku,
                        "barcode": variant.barcode,
                        "available_to_sell": available,
                        "unit_price": as_decimal(variant.price_amount),
                    }
                )
            return items

    def lookup_customers(
        self,
        user: AuthenticatedUser,
        *,
        phone: str = "",
        email: str = "",
    ) -> list[dict[str, Any]]:
        _require_page(user, "Sales")
        phone_normalized = normalize_phone(phone)
        email_normalized = normalize_email(email)
        _require(
            bool(phone_normalized or email_normalized),
            message="Phone or email is required to search customers",
        )
        with self._session_factory() as session:
            stmt = select(CustomerModel).where(
                CustomerModel.client_id == user.client_id,
                CustomerModel.status == "active",
            )
            filters = []
            if phone_normalized:
                filters.append(CustomerModel.phone_normalized.like(f"{phone_normalized}%"))
            if email_normalized:
                filters.append(CustomerModel.email_normalized.like(f"{email_normalized}%"))
            stmt = stmt.where(or_(*filters)).order_by(CustomerModel.updated_at.desc()).limit(10)
            customers = session.execute(stmt).scalars().all()
            return [
                {
                    "customer_id": str(customer.customer_id),
                    "name": customer.name,
                    "phone": customer.phone,
                    "email": customer.email,
                }
                for customer in customers
            ]

    def _resolve_customer(
        self,
        session: Session,
        user: AuthenticatedUser,
        *,
        customer_id: str | None,
        customer_payload: dict[str, Any] | None,
    ) -> CustomerModel:
        if customer_id:
            customer = session.execute(
                select(CustomerModel).where(
                    CustomerModel.client_id == user.client_id,
                    CustomerModel.customer_id == customer_id,
                    CustomerModel.status == "active",
                )
            ).scalar_one_or_none()
            _require(customer is not None, message="Customer not found", code="CUSTOMER_NOT_FOUND", status_code=404)
            return customer

        _require(customer_payload is not None, message="Customer details are required")
        phone = str(customer_payload.get("phone", "")).strip()
        email = str(customer_payload.get("email", "")).strip()
        normalized_phone = normalize_phone(phone)
        normalized_email = normalize_email(email)
        _require(bool(normalized_phone or normalized_email), message="Customer phone or email is required")
        existing = None
        if normalized_phone:
            existing = session.execute(
                select(CustomerModel).where(
                    CustomerModel.client_id == user.client_id,
                    CustomerModel.phone_normalized == normalized_phone,
                )
            ).scalar_one_or_none()
        if existing is None and normalized_email:
            existing = session.execute(
                select(CustomerModel).where(
                    CustomerModel.client_id == user.client_id,
                    CustomerModel.email_normalized == normalized_email,
                )
            ).scalar_one_or_none()
        if existing:
            if not existing.email and email:
                existing.email = email
                existing.email_normalized = normalized_email
            if not existing.phone and phone:
                existing.phone = phone
                existing.phone_normalized = normalized_phone
            if not existing.address and customer_payload.get("address"):
                existing.address = str(customer_payload.get("address", "")).strip()
            return existing
        customer = CustomerModel(
            customer_id=new_uuid(),
            client_id=user.client_id,
            code=slugify_identifier(
                f"{customer_payload['name']}-{normalized_phone or normalized_email}",
                max_length=64,
                default="customer",
            ),
            name=str(customer_payload["name"]).strip(),
            email=email,
            email_normalized=normalized_email,
            phone=phone,
            phone_normalized=normalized_phone,
            address=str(customer_payload.get("address", "")).strip(),
            status="active",
        )
        session.add(customer)
        session.flush()
        return customer

    def _upsert_order(
        self,
        session: Session,
        user: AuthenticatedUser,
        *,
        sales_order_id: str | None,
        location_id: str | None,
        customer_id: str | None,
        customer_payload: dict[str, Any] | None,
        payment_status: str,
        shipment_status: str,
        notes: str,
        lines: list[dict[str, Any]],
        action: str,
    ) -> SalesOrderModel:
        _require(bool(lines), message="At least one order line is required")
        location_context = self._location_context(session, user.client_id, location_id)
        order = None
        if sales_order_id:
            order = session.execute(
                select(SalesOrderModel).where(
                    SalesOrderModel.client_id == user.client_id,
                    SalesOrderModel.sales_order_id == sales_order_id,
                )
            ).scalar_one_or_none()
            _require(order is not None, message="Order not found", code="ORDER_NOT_FOUND", status_code=404)
            _require(order.status == "draft", message="Only draft orders can be edited")
            session.execute(
                select(SalesOrderItemModel)
                .where(
                    SalesOrderItemModel.client_id == user.client_id,
                    SalesOrderItemModel.sales_order_id == order.sales_order_id,
                )
            ).scalars().all()
            for existing_item in session.execute(
                select(SalesOrderItemModel).where(
                    SalesOrderItemModel.client_id == user.client_id,
                    SalesOrderItemModel.sales_order_id == order.sales_order_id,
                )
            ).scalars():
                session.delete(existing_item)
        else:
            settings = self._client_settings(session, user.client_id)
            prefix = settings.order_prefix if settings else "SO"
            order = SalesOrderModel(
                sales_order_id=new_uuid(),
                client_id=user.client_id,
                order_number=_new_number(prefix),
                created_by_user_id=user.user_id,
            )
            session.add(order)

        order.location_id = location_context.active_location_id
        order.payment_status = payment_status or "unpaid"
        order.shipment_status = shipment_status or "pending"
        order.notes = notes.strip()
        order.ordered_at = order.ordered_at or now_utc()
        order.status = "draft"
        order.confirmed_at = None
        order.discount_amount = ZERO
        order.paid_amount = ZERO

        customer = self._resolve_customer(
            session,
            user,
            customer_id=customer_id,
            customer_payload=customer_payload,
        )
        order.customer_id = customer.customer_id
        session.flush()

        subtotal = ZERO
        total_discount = ZERO
        for line in lines:
            variant = session.execute(
                select(ProductVariantModel).where(
                    ProductVariantModel.client_id == user.client_id,
                    ProductVariantModel.variant_id == line["variant_id"],
                    ProductVariantModel.status == "active",
                )
            ).scalar_one_or_none()
            _require(variant is not None, message="Variant not found", code="VARIANT_NOT_FOUND", status_code=404)
            quantity = as_decimal(line["quantity"])
            discount_amount = as_decimal(line.get("discount_amount"))
            unit_price = as_decimal(line.get("unit_price")) or as_decimal(variant.price_amount)
            line_total = quantity * unit_price - discount_amount
            _require(line_total >= ZERO, message="Line total cannot be negative")
            subtotal += quantity * unit_price
            total_discount += discount_amount
            session.add(
                SalesOrderItemModel(
                    sales_order_item_id=new_uuid(),
                    client_id=user.client_id,
                    sales_order_id=order.sales_order_id,
                    variant_id=variant.variant_id,
                    quantity=quantity,
                    quantity_fulfilled=ZERO,
                    quantity_cancelled=ZERO,
                    unit_price_amount=unit_price,
                    discount_amount=discount_amount,
                    line_total_amount=line_total,
                )
            )
        order.subtotal_amount = subtotal
        order.discount_amount = total_discount
        order.total_amount = subtotal - total_discount
        session.flush()

        if action in {"confirm", "confirm_and_fulfill"}:
            order.status = "confirmed"
            order.confirmed_at = now_utc()
            self._validate_available_stock(session, user, order)
        if action == "confirm_and_fulfill":
            self._fulfill_order(session, user, order)
        return order

    def _validate_available_stock(self, session: Session, user: AuthenticatedUser, order: SalesOrderModel) -> None:
        on_hand_map, _reserved_map = self._stock_maps(session, user.client_id, str(order.location_id))
        reserved_without_current = {
            str(variant_id): as_decimal(quantity)
            for variant_id, quantity in session.execute(
                select(
                    SalesOrderItemModel.variant_id,
                    func.coalesce(
                        func.sum(
                            SalesOrderItemModel.quantity
                            - SalesOrderItemModel.quantity_fulfilled
                            - SalesOrderItemModel.quantity_cancelled
                        ),
                        ZERO,
                    ),
                )
                .join(SalesOrderModel, SalesOrderModel.sales_order_id == SalesOrderItemModel.sales_order_id)
                .where(
                    SalesOrderItemModel.client_id == user.client_id,
                    SalesOrderModel.client_id == user.client_id,
                    SalesOrderModel.location_id == order.location_id,
                    SalesOrderModel.status == "confirmed",
                    SalesOrderModel.sales_order_id != order.sales_order_id,
                )
                .group_by(SalesOrderItemModel.variant_id)
            ).all()
        }
        for item in session.execute(
            select(SalesOrderItemModel).where(
                SalesOrderItemModel.client_id == user.client_id,
                SalesOrderItemModel.sales_order_id == order.sales_order_id,
            )
        ).scalars():
            variant_id = str(item.variant_id)
            available = on_hand_map.get(variant_id, ZERO) - reserved_without_current.get(variant_id, ZERO)
            _require(
                available >= as_decimal(item.quantity),
                message="Insufficient available stock to confirm the order",
                code="INSUFFICIENT_STOCK",
            )

    def _fulfill_order(self, session: Session, user: AuthenticatedUser, order: SalesOrderModel) -> None:
        _require(order.status == "confirmed", message="Only confirmed orders can be fulfilled")
        items = session.execute(
            select(SalesOrderItemModel, ProductVariantModel)
            .join(ProductVariantModel, ProductVariantModel.variant_id == SalesOrderItemModel.variant_id)
            .where(
                SalesOrderItemModel.client_id == user.client_id,
                SalesOrderItemModel.sales_order_id == order.sales_order_id,
            )
        ).all()
        for item, variant in items:
            remaining = as_decimal(item.quantity) - as_decimal(item.quantity_fulfilled) - as_decimal(item.quantity_cancelled)
            if remaining <= ZERO:
                continue
            session.add(
                InventoryLedgerModel(
                    entry_id=new_uuid(),
                    client_id=user.client_id,
                    variant_id=variant.variant_id,
                    location_id=order.location_id,
                    movement_type="sale_fulfilled",
                    reference_type="sales_order",
                    reference_id=str(order.sales_order_id),
                    reference_line_id=str(item.sales_order_item_id),
                    quantity_delta=-remaining,
                    unit_cost_amount=as_decimal(variant.cost_amount),
                    unit_price_amount=as_decimal(item.unit_price_amount),
                    reason="Order fulfilled",
                    created_by_user_id=user.user_id,
                )
            )
            item.quantity_fulfilled = as_decimal(item.quantity_fulfilled) + remaining
        order.shipment_status = "fulfilled"
        order.status = "completed"
        shipment = ShipmentModel(
            shipment_id=new_uuid(),
            client_id=user.client_id,
            sales_order_id=order.sales_order_id,
            status="delivered",
            shipped_at=now_utc(),
            delivered_at=now_utc(),
            notes="Whole-order fulfillment",
        )
        session.add(shipment)

    def create_order(
        self,
        user: AuthenticatedUser,
        *,
        location_id: str | None,
        customer_id: str | None,
        customer_payload: dict[str, Any] | None,
        payment_status: str,
        shipment_status: str,
        notes: str,
        lines: list[dict[str, Any]],
        action: str,
    ) -> dict[str, Any]:
        _require_page(user, "Sales")
        with self._session_factory() as session:
            order = self._upsert_order(
                session,
                user,
                sales_order_id=None,
                location_id=location_id,
                customer_id=customer_id,
                customer_payload=customer_payload,
                payment_status=payment_status,
                shipment_status=shipment_status,
                notes=notes,
                lines=lines,
                action=action,
            )
            session.commit()
            return self._sales_order_payload(session, order)

    def update_order(
        self,
        user: AuthenticatedUser,
        *,
        sales_order_id: str,
        location_id: str | None,
        customer_id: str | None,
        customer_payload: dict[str, Any] | None,
        payment_status: str,
        shipment_status: str,
        notes: str,
        lines: list[dict[str, Any]],
        action: str,
    ) -> dict[str, Any]:
        _require_page(user, "Sales")
        with self._session_factory() as session:
            order = self._upsert_order(
                session,
                user,
                sales_order_id=sales_order_id,
                location_id=location_id,
                customer_id=customer_id,
                customer_payload=customer_payload,
                payment_status=payment_status,
                shipment_status=shipment_status,
                notes=notes,
                lines=lines,
                action=action,
            )
            session.commit()
            return self._sales_order_payload(session, order)

    def confirm_order(self, user: AuthenticatedUser, sales_order_id: str) -> dict[str, Any]:
        _require_page(user, "Sales")
        with self._session_factory() as session:
            order = session.execute(
                select(SalesOrderModel).where(
                    SalesOrderModel.client_id == user.client_id,
                    SalesOrderModel.sales_order_id == sales_order_id,
                )
            ).scalar_one_or_none()
            _require(order is not None, message="Order not found", code="ORDER_NOT_FOUND", status_code=404)
            _require(order.status == "draft", message="Only draft orders can be confirmed")
            self._validate_available_stock(session, user, order)
            order.status = "confirmed"
            order.confirmed_at = now_utc()
            session.commit()
            return self._sales_order_payload(session, order)

    def fulfill_order(self, user: AuthenticatedUser, sales_order_id: str) -> dict[str, Any]:
        _require_page(user, "Sales")
        with self._session_factory() as session:
            order = session.execute(
                select(SalesOrderModel).where(
                    SalesOrderModel.client_id == user.client_id,
                    SalesOrderModel.sales_order_id == sales_order_id,
                )
            ).scalar_one_or_none()
            _require(order is not None, message="Order not found", code="ORDER_NOT_FOUND", status_code=404)
            self._fulfill_order(session, user, order)
            session.commit()
            return self._sales_order_payload(session, order)

    def cancel_order(self, user: AuthenticatedUser, sales_order_id: str, *, notes: str | None = None) -> dict[str, Any]:
        _require_page(user, "Sales")
        with self._session_factory() as session:
            order = session.execute(
                select(SalesOrderModel).where(
                    SalesOrderModel.client_id == user.client_id,
                    SalesOrderModel.sales_order_id == sales_order_id,
                )
            ).scalar_one_or_none()
            _require(order is not None, message="Order not found", code="ORDER_NOT_FOUND", status_code=404)
            _require(order.status in {"draft", "confirmed"}, message="Only open orders can be cancelled")
            for item in session.execute(
                select(SalesOrderItemModel).where(
                    SalesOrderItemModel.client_id == user.client_id,
                    SalesOrderItemModel.sales_order_id == sales_order_id,
                )
            ).scalars():
                remaining = as_decimal(item.quantity) - as_decimal(item.quantity_fulfilled)
                item.quantity_cancelled = max(ZERO, remaining)
            order.status = "cancelled"
            if notes:
                order.notes = "\n".join(filter(None, [order.notes.strip(), notes.strip()]))
            session.commit()
            return self._sales_order_payload(session, order)


class ReturnsService(CommerceBaseService):
    def _eligible_lines_payload(
        self,
        session: Session,
        user: AuthenticatedUser,
        sales_order_id: str,
    ) -> dict[str, Any]:
        order_row = session.execute(
            select(SalesOrderModel, CustomerModel)
            .join(CustomerModel, CustomerModel.customer_id == SalesOrderModel.customer_id)
            .where(
                SalesOrderModel.client_id == user.client_id,
                SalesOrderModel.sales_order_id == sales_order_id,
            )
        ).first()
        _require(order_row is not None, message="Order not found", code="ORDER_NOT_FOUND", status_code=404)
        order, customer = order_row
        returned_quantities = {
            str(item_id): as_decimal(quantity)
            for item_id, quantity in session.execute(
                select(
                    SalesReturnItemModel.sales_order_item_id,
                    func.coalesce(func.sum(SalesReturnItemModel.quantity), ZERO),
                )
                .join(SalesReturnModel, SalesReturnModel.sales_return_id == SalesReturnItemModel.sales_return_id)
                .where(
                    SalesReturnModel.client_id == user.client_id,
                    SalesReturnModel.sales_order_id == sales_order_id,
                )
                .group_by(SalesReturnItemModel.sales_order_item_id)
            ).all()
            if item_id is not None
        }
        line_rows = session.execute(
            select(SalesOrderItemModel, ProductVariantModel, ProductModel)
            .join(ProductVariantModel, ProductVariantModel.variant_id == SalesOrderItemModel.variant_id)
            .join(ProductModel, ProductModel.product_id == ProductVariantModel.product_id)
            .where(
                SalesOrderItemModel.client_id == user.client_id,
                SalesOrderItemModel.sales_order_id == sales_order_id,
            )
        ).all()
        lines = []
        for item, variant, product in line_rows:
            returned = returned_quantities.get(str(item.sales_order_item_id), ZERO)
            eligible = as_decimal(item.quantity_fulfilled) - returned
            if eligible <= ZERO:
                continue
            lines.append(
                {
                    "sales_order_item_id": str(item.sales_order_item_id),
                    "variant_id": str(variant.variant_id),
                    "product_name": product.name,
                    "label": build_variant_label(product.name, variant.title),
                    "quantity": as_decimal(item.quantity),
                    "quantity_fulfilled": as_decimal(item.quantity_fulfilled),
                    "quantity_returned": returned,
                    "eligible_quantity": eligible,
                    "unit_price": as_decimal(item.unit_price_amount),
                }
            )
        return {
            "sales_order_id": str(order.sales_order_id),
            "order_number": order.order_number,
            "customer_name": customer.name,
            "customer_phone": customer.phone,
            "lines": lines,
        }

    def list_returns(self, user: AuthenticatedUser, *, query: str = "") -> list[dict[str, Any]]:
        _require_page(user, "Returns")
        with self._session_factory() as session:
            stmt = select(SalesReturnModel).where(SalesReturnModel.client_id == user.client_id)
            trimmed = query.strip().lower()
            if trimmed:
                pattern = f"%{trimmed}%"
                stmt = (
                    stmt.outerjoin(SalesOrderModel, SalesOrderModel.sales_order_id == SalesReturnModel.sales_order_id)
                    .outerjoin(CustomerModel, CustomerModel.customer_id == SalesReturnModel.customer_id)
                    .where(
                        or_(
                            func.lower(SalesReturnModel.return_number).like(pattern),
                            func.lower(SalesOrderModel.order_number).like(pattern),
                            func.lower(CustomerModel.phone).like(pattern),
                            func.lower(CustomerModel.email).like(pattern),
                        )
                    )
                )
            records = session.execute(stmt.order_by(SalesReturnModel.created_at.desc())).scalars().all()
            return [self._return_payload(session, record) for record in records]

    def eligible_orders(self, user: AuthenticatedUser, *, query: str) -> list[dict[str, Any]]:
        _require_page(user, "Returns")
        trimmed = query.strip().lower()
        _require(bool(trimmed), message="Order number, phone, or email is required")
        with self._session_factory() as session:
            pattern = f"%{trimmed}%"
            orders = session.execute(
                select(SalesOrderModel, CustomerModel)
                .join(CustomerModel, CustomerModel.customer_id == SalesOrderModel.customer_id)
                .where(
                    SalesOrderModel.client_id == user.client_id,
                    SalesOrderModel.status == "completed",
                    or_(
                        func.lower(SalesOrderModel.order_number).like(pattern),
                        func.lower(CustomerModel.phone).like(pattern),
                        func.lower(CustomerModel.email).like(pattern),
                    ),
                )
                .order_by(SalesOrderModel.created_at.desc())
            ).all()
            items = []
            for order, customer in orders:
                items.append(
                    {
                        "sales_order_id": str(order.sales_order_id),
                        "order_number": order.order_number,
                        "customer_name": customer.name,
                        "customer_phone": customer.phone,
                        "customer_email": customer.email,
                        "ordered_at": order.ordered_at.isoformat() if order.ordered_at else None,
                        "total_amount": as_decimal(order.total_amount),
                        "status": order.status,
                        "shipment_status": order.shipment_status,
                    }
                )
            return items

    def eligible_lines(self, user: AuthenticatedUser, sales_order_id: str) -> dict[str, Any]:
        _require_page(user, "Returns")
        with self._session_factory() as session:
            return self._eligible_lines_payload(session, user, sales_order_id)

    def create_return(
        self,
        user: AuthenticatedUser,
        *,
        sales_order_id: str,
        notes: str,
        refund_status: str,
        lines: list[dict[str, Any]],
    ) -> dict[str, Any]:
        _require_page(user, "Returns")
        _require(bool(lines), message="At least one return line is required")
        with self._session_factory() as session:
            order = session.execute(
                select(SalesOrderModel).where(
                    SalesOrderModel.client_id == user.client_id,
                    SalesOrderModel.sales_order_id == sales_order_id,
                )
            ).scalar_one_or_none()
            _require(order is not None, message="Order not found", code="ORDER_NOT_FOUND", status_code=404)
            customer = None
            if order.customer_id:
                customer = session.execute(
                    select(CustomerModel).where(
                        CustomerModel.client_id == user.client_id,
                        CustomerModel.customer_id == order.customer_id,
                    )
                ).scalar_one_or_none()
            settings = self._client_settings(session, user.client_id)
            prefix = settings.return_prefix if settings else "RT"
            return_record = SalesReturnModel(
                sales_return_id=new_uuid(),
                client_id=user.client_id,
                sales_order_id=order.sales_order_id,
                customer_id=order.customer_id,
                return_number=_new_number(prefix),
                status="received",
                refund_status=refund_status or "pending",
                requested_at=now_utc(),
                received_at=now_utc(),
                notes=notes.strip(),
                created_by_user_id=user.user_id,
            )
            session.add(return_record)
            session.flush()

            eligible = self._eligible_lines_payload(session, user, sales_order_id)
            eligible_by_item = {line["sales_order_item_id"]: line for line in eligible["lines"]}
            subtotal = ZERO
            refund_total = ZERO
            for line in lines:
                eligible_line = eligible_by_item.get(str(line["sales_order_item_id"]))
                _require(eligible_line is not None, message="Return line is not eligible")
                quantity = as_decimal(line["quantity"])
                restock_quantity = as_decimal(line.get("restock_quantity"))
                _require(restock_quantity <= quantity, message="Restock quantity cannot exceed return quantity")
                _require(quantity <= as_decimal(eligible_line["eligible_quantity"]), message="Return quantity exceeds eligible quantity")
                order_item = session.execute(
                    select(SalesOrderItemModel).where(
                        SalesOrderItemModel.client_id == user.client_id,
                        SalesOrderItemModel.sales_order_item_id == line["sales_order_item_id"],
                    )
                ).scalar_one()
                return_item = SalesReturnItemModel(
                    sales_return_item_id=new_uuid(),
                    client_id=user.client_id,
                    sales_return_id=return_record.sales_return_id,
                    sales_order_item_id=order_item.sales_order_item_id,
                    variant_id=order_item.variant_id,
                    quantity=quantity,
                    restock_quantity=restock_quantity,
                    unit_refund_amount=as_decimal(line.get("unit_refund_amount")) or as_decimal(order_item.unit_price_amount),
                    disposition=str(line.get("disposition", "restock")).strip() or "restock",
                )
                session.add(return_item)
                line_total = quantity * as_decimal(return_item.unit_refund_amount)
                subtotal += line_total
                refund_total += line_total
                if restock_quantity > ZERO:
                    variant = session.execute(
                        select(ProductVariantModel).where(ProductVariantModel.variant_id == order_item.variant_id)
                    ).scalar_one()
                    session.add(
                        InventoryLedgerModel(
                            entry_id=new_uuid(),
                            client_id=user.client_id,
                            variant_id=variant.variant_id,
                            location_id=order.location_id,
                            movement_type="sales_return_restock",
                            reference_type="sales_return",
                            reference_id=str(return_record.sales_return_id),
                            reference_line_id=str(return_item.sales_return_item_id),
                            quantity_delta=restock_quantity,
                            unit_cost_amount=as_decimal(variant.cost_amount),
                            unit_price_amount=as_decimal(return_item.unit_refund_amount),
                            reason=str(line.get("reason", "")).strip() or "Return restocked",
                            created_by_user_id=user.user_id,
                        )
                    )

            return_record.subtotal_amount = subtotal
            return_record.refund_amount = refund_total
            session.commit()
            return self._return_payload(session, return_record)
