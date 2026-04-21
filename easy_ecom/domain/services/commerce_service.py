from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Select, delete, func, or_, select
from sqlalchemy.orm import Session, sessionmaker

from easy_ecom.core.errors import ApiException
from easy_ecom.core.ids import new_uuid
from easy_ecom.core.slugs import slugify_identifier
from easy_ecom.core.time_utils import now_utc
from easy_ecom.data.store.postgres_models import (
    CategoryModel,
    ClientSettingsModel,
    CustomerModel,
    FinanceTransactionModel,
    InventoryLedgerModel,
    LocationModel,
    PaymentModel,
    ProductModel,
    ProductVariantModel,
    PurchaseItemModel,
    PurchaseModel,
    RefundModel,
    SalesOrderItemModel,
    SalesOrderModel,
    SalesReturnItemModel,
    SalesReturnModel,
    ShipmentModel,
    SupplierModel,
)
from easy_ecom.domain.models.auth import AuthenticatedUser
from easy_ecom.domain.services.finance_posting_service import FinancePostingService
from easy_ecom.domain.services.product_media_service import ProductMediaService


ZERO = Decimal("0")
MONEY_QUANTUM = Decimal("0.01")


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


def as_optional_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, str) and not value.strip():
        return None
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


def build_sku_base(value: str) -> str:
    token = slugify_identifier(value.strip(), max_length=64, default="")
    return token.upper()


def build_sku_token(value: str) -> str:
    token = slugify_identifier(value.strip(), max_length=24, default="")
    return token.upper()


def build_sku_candidate(product_name: str, sku_root: str, size: str, color: str, other: str) -> str:
    base = build_sku_base(sku_root or product_name)
    parts = [base]
    for part in (size, color, other):
        token = build_sku_token(part)
        if token:
            parts.append(token)
    normalized = [part for part in parts if part]
    return "-".join(normalized) if normalized else new_uuid()[:8].upper()


def normalize_lookup_text(value: str) -> str:
    return " ".join(value.strip().lower().split())


def build_variant_signature(size: str, color: str, other: str) -> str:
    return "|".join(normalize_lookup_text(part) for part in (size, color, other))


def derive_discount_percent(default_price: Decimal | None, min_price: Decimal | None) -> Decimal | None:
    if default_price is None or min_price is None or default_price <= ZERO:
        return None
    discount = ((default_price - min_price) / default_price) * Decimal("100")
    if discount < ZERO:
        return ZERO
    return discount.quantize(MONEY_QUANTUM)


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
        self._finance_posting = FinancePostingService()
        self._product_media = ProductMediaService()

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

    def _base_product_stmt(self, client_id: str) -> Select[tuple[ProductModel, SupplierModel | None, CategoryModel | None]]:
        return (
            select(ProductModel, SupplierModel, CategoryModel)
            .outerjoin(SupplierModel, SupplierModel.supplier_id == ProductModel.supplier_id)
            .outerjoin(CategoryModel, CategoryModel.category_id == ProductModel.category_id)
            .where(ProductModel.client_id == client_id)
            .order_by(ProductModel.name.asc())
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

    def _effective_variant_price(self, product: ProductModel, variant: ProductVariantModel) -> Decimal | None:
        return as_optional_decimal(variant.price_amount) if variant.price_amount is not None else as_optional_decimal(product.default_price_amount)

    def _effective_variant_min_price(self, product: ProductModel, variant: ProductVariantModel) -> Decimal | None:
        return as_optional_decimal(variant.min_price_amount) if variant.min_price_amount is not None else as_optional_decimal(product.min_price_amount)

    def _normalize_product_pricing(self, identity: dict[str, Any]) -> tuple[Decimal | None, Decimal | None, Decimal | None]:
        default_price = as_optional_decimal(identity.get("default_selling_price"))
        min_price = as_optional_decimal(identity.get("min_selling_price"))
        legacy_discount = as_optional_decimal(identity.get("max_discount_percent"))

        if default_price is not None:
            _require(default_price >= ZERO, message="Default selling price cannot be negative")
        if min_price is not None:
            _require(min_price >= ZERO, message="Minimum selling price cannot be negative")
        if legacy_discount is not None:
            _require(legacy_discount >= ZERO, message="Max discount percent cannot be negative")

        if legacy_discount is not None and default_price is None:
            raise ApiException(
                status_code=400,
                code="INVALID_PRICING",
                message="Max discount percent requires a default selling price",
            )
        if legacy_discount is not None and min_price is None and default_price is not None:
            min_price = (default_price * (Decimal("100") - legacy_discount) / Decimal("100")).quantize(MONEY_QUANTUM)
        if default_price is not None and min_price is not None:
            _require(min_price <= default_price, message="Minimum selling price cannot exceed default selling price")
        derived_discount = derive_discount_percent(default_price, min_price)
        if legacy_discount is not None and derived_discount is not None:
            delta = abs(legacy_discount - derived_discount)
            _require(delta <= MONEY_QUANTUM, message="Minimum price conflicts with max discount percent")
        return default_price, min_price, derived_discount

    def _normalize_variant_pricing(
        self,
        variant_payload: dict[str, Any],
    ) -> tuple[Decimal | None, Decimal | None, Decimal | None]:
        cost = as_optional_decimal(variant_payload.get("default_purchase_price"))
        price = as_optional_decimal(variant_payload.get("default_selling_price"))
        min_price = as_optional_decimal(variant_payload.get("min_selling_price"))
        if cost is not None:
            _require(cost >= ZERO, message="Default purchase cost cannot be negative")
        if price is not None:
            _require(price >= ZERO, message="Default selling price cannot be negative")
        if min_price is not None:
            _require(min_price >= ZERO, message="Minimum selling price cannot be negative")
        if price is not None and min_price is not None:
            _require(min_price <= price, message="Variant minimum selling price cannot exceed variant price")
        return cost, price, min_price

    def _generate_unique_sku(
        self,
        session: Session,
        client_id: str,
        *,
        product_name: str,
        sku_root: str,
        size: str,
        color: str,
        other: str,
        exclude_variant_id: str | None = None,
    ) -> str:
        base_sku = build_sku_candidate(product_name, sku_root, size, color, other)
        candidate = base_sku
        suffix = 2
        while True:
            existing = session.execute(
                select(ProductVariantModel).where(
                    ProductVariantModel.client_id == client_id,
                    ProductVariantModel.sku == candidate,
                )
            ).scalar_one_or_none()
            if existing is None or str(existing.variant_id) == exclude_variant_id:
                return candidate
            candidate = f"{base_sku}-{suffix}"
            suffix += 1

    def _variant_has_stock(self, session: Session, client_id: str, variant_id: str) -> bool:
        stock = session.execute(
            select(func.coalesce(func.sum(InventoryLedgerModel.quantity_delta), ZERO)).where(
                InventoryLedgerModel.client_id == client_id,
                InventoryLedgerModel.variant_id == variant_id,
            )
        ).scalar_one()
        reserved = session.execute(
            select(
                func.coalesce(
                    func.sum(
                        SalesOrderItemModel.quantity
                        - SalesOrderItemModel.quantity_fulfilled
                        - SalesOrderItemModel.quantity_cancelled
                    ),
                    ZERO,
                )
            )
            .join(SalesOrderModel, SalesOrderModel.sales_order_id == SalesOrderItemModel.sales_order_id)
            .where(
                SalesOrderItemModel.client_id == client_id,
                SalesOrderItemModel.variant_id == variant_id,
                SalesOrderModel.client_id == client_id,
                SalesOrderModel.status == "confirmed",
            )
        ).scalar_one()
        return as_decimal(stock) > ZERO or as_decimal(reserved) > ZERO

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
        explicit_price = as_optional_decimal(variant.price_amount)
        explicit_min_price = as_optional_decimal(variant.min_price_amount)
        effective_price = self._effective_variant_price(product, variant)
        effective_min_price = self._effective_variant_min_price(product, variant)
        return {
            "variant_id": str(variant.variant_id),
            "product_id": str(product.product_id),
            "product_name": product.name,
            "title": variant.title,
            "label": build_variant_label(product.name, variant.title),
            "sku": variant.sku,
            "status": variant.status,
            "options": {
                "size": size,
                "color": color,
                "other": other,
            },
            "unit_cost": as_optional_decimal(variant.cost_amount),
            "unit_price": explicit_price,
            "min_price": explicit_min_price,
            "effective_unit_price": effective_price,
            "effective_min_price": effective_min_price,
            "is_price_inherited": explicit_price is None and effective_price is not None,
            "is_min_price_inherited": explicit_min_price is None and effective_min_price is not None,
            "reorder_level": as_decimal(variant.reorder_level),
            "on_hand": on_hand,
            "reserved": reserved,
            "available_to_sell": on_hand - reserved,
        }

    def _product_media_payload_map(
        self,
        session: Session,
        client_id: str,
        products: list[ProductModel],
    ) -> dict[str, dict[str, Any]]:
        media_ids = {
            str(product.primary_media_id)
            for product in products
            if product.primary_media_id
        }
        return self._product_media.media_payload_map(session, client_id=client_id, media_ids=media_ids)

    def _product_payload_from_rows(
        self,
        client_id: str,
        rows: list[tuple[ProductModel, ProductVariantModel, SupplierModel | None, CategoryModel | None]],
        on_hand_map: dict[str, Decimal],
        reserved_map: dict[str, Decimal],
        media_payload_map: dict[str, dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        _require(bool(rows), message="Product not found", code="PRODUCT_NOT_FOUND", status_code=404)
        product, _variant, supplier, category = rows[0]
        image_payload = None
        if product.primary_media_id and media_payload_map:
            image_payload = media_payload_map.get(str(product.primary_media_id))
        payload = self._base_product_payload(product, supplier, category, image_payload)
        for current_product, variant, _supplier, _category in rows:
            payload["variants"].append(
                self._variant_payload(
                    current_product,
                    variant,
                    on_hand_map.get(str(variant.variant_id), ZERO),
                    reserved_map.get(str(variant.variant_id), ZERO),
                )
            )
        return payload

    def _base_product_payload(
        self,
        product: ProductModel,
        supplier: SupplierModel | None,
        category: CategoryModel | None,
        image_payload: dict[str, Any] | None,
    ) -> dict[str, Any]:
        return {
            "product_id": str(product.product_id),
            "name": product.name,
            "brand": product.brand,
            "status": product.status,
            "supplier": supplier.name if supplier else "",
            "category": category.name if category else "",
            "description": product.description,
            "sku_root": product.sku_root,
            "default_price": as_optional_decimal(product.default_price_amount),
            "min_price": as_optional_decimal(product.min_price_amount),
            "max_discount_percent": derive_discount_percent(
                as_optional_decimal(product.default_price_amount),
                as_optional_decimal(product.min_price_amount),
            ),
            "image_url": image_payload["large_url"] if image_payload else product.image_url,
            "image": image_payload,
            "variants": [],
        }

    def _products_payload_map(
        self,
        session: Session,
        *,
        client_id: str,
        product_ids: list[str],
        on_hand_map: dict[str, Decimal],
        reserved_map: dict[str, Decimal],
        include_oos_variants: bool,
        active_only: bool = True,
    ) -> dict[str, dict[str, Any]]:
        if not product_ids:
            return {}

        product_rows = session.execute(
            self._base_product_stmt(client_id).where(ProductModel.product_id.in_(product_ids))
        ).all()
        products = [row[0] for row in product_rows]
        media_payload_map = self._product_media_payload_map(session, client_id, products)

        payloads: dict[str, dict[str, Any]] = {}
        for product, supplier, category in product_rows:
            if active_only and product.status != "active":
                continue
            image_payload = media_payload_map.get(str(product.primary_media_id)) if product.primary_media_id else None
            payloads[str(product.product_id)] = self._base_product_payload(product, supplier, category, image_payload)

        if not payloads:
            return {}

        variant_rows = session.execute(
            self._base_variant_stmt(client_id).where(ProductModel.product_id.in_(list(payloads.keys())))
        ).all()
        for product, variant, _supplier, _category in variant_rows:
            if active_only and (product.status != "active" or variant.status != "active"):
                continue
            on_hand = on_hand_map.get(str(variant.variant_id), ZERO)
            reserved = reserved_map.get(str(variant.variant_id), ZERO)
            available = on_hand - reserved
            if not include_oos_variants and available <= ZERO:
                continue
            payload = payloads.get(str(product.product_id))
            if payload is None:
                continue
            payload["variants"].append(self._variant_payload(product, variant, on_hand, reserved))

        return payloads

    def _product_payload(
        self,
        session: Session,
        client_id: str,
        product_id: str,
        location_id: str,
    ) -> dict[str, Any]:
        on_hand_map, reserved_map = self._stock_maps(session, client_id, location_id)
        payloads = self._products_payload_map(
            session,
            client_id=client_id,
            product_ids=[product_id],
            on_hand_map=on_hand_map,
            reserved_map=reserved_map,
            include_oos_variants=True,
            active_only=False,
        )
        payload = payloads.get(product_id)
        _require(payload is not None, message="Product not found", code="PRODUCT_NOT_FOUND", status_code=404)
        return payload

    def _apply_product_media_instructions(
        self,
        session: Session,
        *,
        user: AuthenticatedUser,
        product: ProductModel,
        identity: dict[str, Any],
    ) -> None:
        pending_upload_id = str(identity.get("pending_primary_media_upload_id", "") or "").strip()
        remove_primary_image = bool(identity.get("remove_primary_image", False))
        if remove_primary_image:
            self._product_media.remove_primary_media(
                session,
                client_id=user.client_id,
                product_id=str(product.product_id),
            )
        if pending_upload_id:
            self._product_media.attach_staged_upload(
                session,
                client_id=user.client_id,
                product_id=str(product.product_id),
                staged_upload_id=pending_upload_id,
                user_id=user.user_id,
            )

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
        finance_transaction = session.execute(
            select(FinanceTransactionModel)
            .where(
                FinanceTransactionModel.client_id == order.client_id,
                FinanceTransactionModel.origin_type == "sale_fulfillment",
                FinanceTransactionModel.origin_id == order.sales_order_id,
            )
            .order_by(FinanceTransactionModel.occurred_at.desc())
        ).scalars().first()
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
            "source_type": order.source_type,
            "finance_status": "posted" if finance_transaction else "not_posted",
            "finance_summary": (
                {
                    "transaction_id": str(finance_transaction.transaction_id),
                    "origin_type": finance_transaction.origin_type,
                    "amount": as_decimal(finance_transaction.amount),
                    "posted_at": finance_transaction.occurred_at.isoformat(),
                }
                if finance_transaction
                else None
            ),
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
        refunded_total = self._finance_posting.refunded_total(
            session,
            client_id=str(record.client_id),
            sales_return_id=str(record.sales_return_id),
        )
        finance_transaction = session.execute(
            select(FinanceTransactionModel)
            .where(
                FinanceTransactionModel.client_id == record.client_id,
                FinanceTransactionModel.origin_type == "return_refund",
                FinanceTransactionModel.origin_id == record.sales_return_id,
            )
            .order_by(FinanceTransactionModel.occurred_at.desc())
        ).scalars().first()
        recent_refunds = session.execute(
            select(FinanceTransactionModel)
            .where(
                FinanceTransactionModel.client_id == record.client_id,
                FinanceTransactionModel.origin_type == "return_refund",
                FinanceTransactionModel.origin_id == record.sales_return_id,
            )
            .order_by(FinanceTransactionModel.occurred_at.desc(), FinanceTransactionModel.transaction_id.desc())
        ).scalars().all()
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
            "refund_paid_amount": refunded_total,
            "refund_outstanding_amount": max(ZERO, as_decimal(record.refund_amount) - refunded_total),
            "finance_status": "posted" if finance_transaction else "not_posted",
            "requested_at": record.requested_at.isoformat() if record.requested_at else None,
            "received_at": record.received_at.isoformat() if record.received_at else None,
            "recent_refunds": [
                {
                    "transaction_id": str(transaction.transaction_id),
                    "amount": as_decimal(transaction.amount),
                    "reference": transaction.reference,
                    "note": transaction.note,
                    "posted_at": transaction.occurred_at.isoformat() if transaction.occurred_at else None,
                }
                for transaction in recent_refunds
            ],
            "lines": lines,
        }


class CatalogService(CommerceBaseService):
    def validate_product_creation_step(
        self,
        user: AuthenticatedUser,
        *,
        step: str,
        identity: dict[str, Any],
        variants: list[dict[str, Any]],
    ) -> dict[str, Any]:
        _require_page(user, "Catalog")
        step_value = (step or "").strip().lower()
        _require(step_value in {"product", "first_variant", "confirm"}, message="Unsupported catalog creation step")

        product_name = str(identity.get("product_name", "")).strip()
        if step_value in {"product", "first_variant", "confirm"}:
            _require(len(product_name) >= 2, message="Product name must be at least 2 characters")

        if step_value in {"first_variant", "confirm"}:
            _require(bool(variants), message="At least one variant is required")
            first_variant = variants[0]
            first_status = str(first_variant.get("status", "active")).strip() or "active"
            _require(first_status == "active", message="First variant must be active before confirmation")

            size = str(first_variant.get("size", "")).strip()
            color = str(first_variant.get("color", "")).strip()
            other = str(first_variant.get("other", "")).strip()
            has_options = bool(size or color or other)
            _require(
                has_options,
                message="First variant details are required (add at least one option)",
            )

        return {"step": step_value, "valid": True}

    def create_staged_media(self, user: AuthenticatedUser, upload_file) -> dict[str, Any]:
        if "Catalog" not in user.allowed_pages and "Inventory" not in user.allowed_pages and "SUPER_ADMIN" not in user.roles:
            raise ApiException(status_code=403, code="ACCESS_DENIED", message="Access denied for product media upload")
        with self._session_factory() as session:
            payload = self._product_media.create_staged_upload(
                session,
                client_id=user.client_id,
                user_id=user.user_id,
                upload_file=upload_file,
            )
            session.commit()
            return payload

    def attach_product_media(self, user: AuthenticatedUser, *, product_id: str, staged_upload_id: str) -> dict[str, Any]:
        _require_page(user, "Catalog")
        with self._session_factory() as session:
            self._product_media.attach_staged_upload(
                session,
                client_id=user.client_id,
                product_id=product_id,
                staged_upload_id=staged_upload_id,
                user_id=user.user_id,
            )
            session.commit()
            location_context = self._location_context(session, user.client_id)
            return self._product_payload(
                session,
                user.client_id,
                product_id,
                location_context.active_location_id,
            )

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
            trimmed = query.strip().lower()
            product_stmt = self._base_product_stmt(user.client_id).where(ProductModel.status == "active")
            if trimmed:
                pattern = f"%{trimmed}%"
                variant_match_ids = {
                    str(product_id)
                    for product_id, in session.execute(
                        self._apply_variant_search(
                            select(ProductModel.product_id)
                            .join(ProductVariantModel, ProductVariantModel.product_id == ProductModel.product_id)
                            .where(
                                ProductModel.client_id == user.client_id,
                                ProductVariantModel.client_id == user.client_id,
                            ),
                            query,
                        ).distinct()
                    ).all()
                }
                product_stmt = product_stmt.where(
                    or_(
                        func.lower(ProductModel.name).like(pattern),
                        func.lower(ProductModel.brand).like(pattern),
                        func.lower(ProductModel.sku_root).like(pattern),
                        func.lower(SupplierModel.name).like(pattern),
                        func.lower(CategoryModel.name).like(pattern),
                        ProductModel.product_id.in_(variant_match_ids) if variant_match_ids else False,
                    )
                )

            product_rows = session.execute(product_stmt).all()
            ordered_product_ids = [str(product.product_id) for product, _supplier, _category in product_rows]
            payload_map = self._products_payload_map(
                session,
                client_id=user.client_id,
                product_ids=ordered_product_ids,
                on_hand_map=on_hand_map,
                reserved_map=reserved_map,
                include_oos_variants=include_oos,
                active_only=True,
            )
            items = [payload_map[product_id] for product_id in ordered_product_ids if product_id in payload_map]

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
                "items": items,
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
        with self._session_factory() as session:
            default_price, min_price, derived_discount = self._normalize_product_pricing(identity)
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
            product.status = str(identity.get("status", "active")).strip() or "active"
            product.default_price_amount = default_price
            product.min_price_amount = min_price
            product.max_discount_percent = derived_discount
            session.flush()
            self._apply_product_media_instructions(session, user=user, product=product, identity=identity)

            option_signatures: set[tuple[str, str, str]] = set()
            for variant_payload in variants:
                size = str(variant_payload.get("size", "")).strip()
                color = str(variant_payload.get("color", "")).strip()
                other = str(variant_payload.get("other", "")).strip()
                signature = (size.lower(), color.lower(), other.lower())
                _require(signature not in option_signatures, message="Duplicate variant option combination")
                option_signatures.add(signature)

                requested_variant_id = variant_payload.get("variant_id")
                requested_sku = str(variant_payload.get("sku", "") or "").strip()
                current_status = str(variant_payload.get("status", "active")).strip() or "active"
                cost_amount, price_amount, variant_min_price = self._normalize_variant_pricing(variant_payload)

                variant = None
                existing = None
                if requested_variant_id:
                    variant = session.execute(
                        select(ProductVariantModel).where(
                            ProductVariantModel.client_id == user.client_id,
                            ProductVariantModel.variant_id == requested_variant_id,
                        )
                    ).scalar_one_or_none()
                    _require(variant is not None, message="Variant not found", code="VARIANT_NOT_FOUND", status_code=404)
                elif requested_sku:
                    existing = session.execute(
                        select(ProductVariantModel).where(
                            ProductVariantModel.client_id == user.client_id,
                            ProductVariantModel.sku == requested_sku,
                        )
                    ).scalar_one_or_none()
                    if existing is not None and str(existing.product_id) == str(product.product_id):
                        variant = existing

                if variant is None:
                    variant = ProductVariantModel(
                        variant_id=new_uuid(),
                        client_id=user.client_id,
                        product_id=product.product_id,
                    )
                    session.add(variant)

                if requested_sku and (not requested_variant_id or requested_sku != str(variant.sku)):
                    duplicate = session.execute(
                        select(ProductVariantModel).where(
                            ProductVariantModel.client_id == user.client_id,
                            ProductVariantModel.sku == requested_sku,
                        )
                    ).scalar_one_or_none()
                    if duplicate is not None and str(duplicate.variant_id) != str(variant.variant_id):
                        raise ApiException(status_code=400, code="DUPLICATE_SKU", message="Variant SKU already exists")

                if current_status == "archived" and variant.variant_id and self._variant_has_stock(session, user.client_id, str(variant.variant_id)):
                    raise ApiException(
                        status_code=400,
                        code="VARIANT_STOCK_EXISTS",
                        message="Variants with stock or reservations cannot be archived",
                    )

                variant.product_id = product.product_id
                variant.title = build_variant_title(size, color, other)
                if requested_variant_id and variant.sku:
                    final_sku = str(variant.sku)
                elif requested_sku:
                    final_sku = requested_sku
                else:
                    final_sku = self._generate_unique_sku(
                        session,
                        user.client_id,
                        product_name=product.name,
                        sku_root=product.sku_root,
                        size=size,
                        color=color,
                        other=other,
                        exclude_variant_id=str(variant.variant_id),
                    )
                variant.sku = final_sku
                variant.option_values_json = {"size": size, "color": color, "other": other}
                variant.status = current_status
                variant.cost_amount = cost_amount
                variant.price_amount = price_amount
                variant.min_price_amount = variant_min_price
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
            media_payload_map = self._product_media_payload_map(
                session,
                user.client_id,
                [row[0] for row in rows],
            )
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
                effective_price = self._effective_variant_price(product, variant)
                image_payload = media_payload_map.get(str(product.primary_media_id)) if product.primary_media_id else None
                row = {
                    "variant_id": str(variant.variant_id),
                    "product_id": str(product.product_id),
                    "product_name": product.name,
                    "image_url": image_payload["large_url"] if image_payload else product.image_url,
                    "image": image_payload,
                    "label": build_variant_label(product.name, variant.title),
                    "sku": variant.sku,
                    "supplier": supplier.name if supplier else "",
                    "category": category.name if category else "",
                    "location_id": location_context.active_location_id,
                    "location_name": location_context.active_location_name,
                    "unit_cost": as_optional_decimal(variant.cost_amount),
                    "unit_price": effective_price,
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

    def intake_lookup(
        self,
        user: AuthenticatedUser,
        *,
        query: str = "",
        location_id: str | None = None,
    ) -> dict[str, Any]:
        _require_page(user, "Inventory")
        trimmed = query.strip()
        if not trimmed:
            return {
                "query": "",
                "exact_variants": [],
                "product_matches": [],
                "suggested_new_product": None,
            }

        with self._session_factory() as session:
            location_context = self._location_context(session, user.client_id, location_id)
            rows = session.execute(self._apply_variant_search(self._base_variant_stmt(user.client_id), trimmed)).all()
            on_hand_map, reserved_map = self._stock_maps(session, user.client_id, location_context.active_location_id)
            normalized_query = normalize_lookup_text(trimmed)
            raw_query = trimmed.lower()
            exact_variant_refs: list[dict[str, str]] = []
            broad_product_ids: list[str] = []
            broad_product_seen: set[str] = set()

            for product, variant, supplier, category in rows:
                if product.status != "active" or variant.status != "active":
                    continue
                product_id = str(product.product_id)
                if product_id not in broad_product_seen:
                    broad_product_ids.append(product_id)
                    broad_product_seen.add(product_id)

                match_reason = None
                if variant.sku.lower() == raw_query:
                    match_reason = "sku"
                elif normalize_lookup_text(build_variant_label(product.name, variant.title)) == normalized_query:
                    match_reason = "product_variant"
                if match_reason is None:
                    continue

                exact_variant_refs.append(
                    {
                        "match_reason": match_reason,
                        "product_id": product_id,
                        "variant_id": str(variant.variant_id),
                    }
                )

            pattern = f"%{trimmed.lower()}%"
            product_rows = session.execute(
                self._base_product_stmt(user.client_id)
                .where(ProductModel.status == "active")
                .where(
                    or_(
                        func.lower(ProductModel.name).like(pattern),
                        func.lower(ProductModel.brand).like(pattern),
                        func.lower(ProductModel.sku_root).like(pattern),
                        func.lower(SupplierModel.name).like(pattern),
                        func.lower(CategoryModel.name).like(pattern),
                    )
                )
            ).all()
            for product, _supplier, _category in product_rows:
                product_id = str(product.product_id)
                if product_id in broad_product_seen:
                    continue
                broad_product_ids.append(product_id)
                broad_product_seen.add(product_id)

            product_payloads = self._products_payload_map(
                session,
                client_id=user.client_id,
                product_ids=broad_product_ids,
                on_hand_map=on_hand_map,
                reserved_map=reserved_map,
                include_oos_variants=True,
                active_only=True,
            )
            exact_variants: list[dict[str, Any]] = []
            exact_product_ids: set[str] = set()
            for ref in exact_variant_refs:
                payload = product_payloads.get(ref["product_id"])
                if payload is None:
                    continue
                matched_variant = next(
                    (item for item in payload["variants"] if item["variant_id"] == ref["variant_id"]),
                    None,
                )
                if matched_variant is None:
                    continue
                exact_variants.append(
                    {
                        "match_reason": ref["match_reason"],
                        "product": payload,
                        "variant": matched_variant,
                    }
                )
                exact_product_ids.add(ref["product_id"])

            reason_priority = {"sku": 0, "product_variant": 1}
            exact_variants.sort(
                key=lambda item: (
                    reason_priority.get(str(item["match_reason"]), 99),
                    str(item["product"]["name"]).lower(),
                    str(item["variant"]["label"]).lower(),
                )
            )

            return {
                "query": trimmed,
                "exact_variants": exact_variants,
                "product_matches": [
                    product_payloads[product_id]
                    for product_id in broad_product_ids
                    if product_id not in exact_product_ids and product_id in product_payloads
                ],
                "suggested_new_product": {
                    "product_name": trimmed,
                    "sku_root": build_sku_base(trimmed),
                },
            }

    def _can_save_template_only(self, user: AuthenticatedUser) -> bool:
        return "SUPER_ADMIN" in user.roles or "CLIENT_OWNER" in user.roles

    def _resolve_receive_product(
        self,
        session: Session,
        user: AuthenticatedUser,
        identity: dict[str, Any],
        lines: list[dict[str, Any]],
    ) -> ProductModel | None:
        requested_product_id = str(identity.get("product_id", "") or "").strip()
        if requested_product_id:
            product = session.execute(
                select(ProductModel).where(
                    ProductModel.client_id == user.client_id,
                    ProductModel.product_id == requested_product_id,
                )
            ).scalar_one_or_none()
            _require(product is not None, message="Product not found", code="PRODUCT_NOT_FOUND", status_code=404)
            return product

        for line in lines:
            requested_variant_id = str(line.get("variant_id", "") or "").strip()
            if not requested_variant_id:
                continue
            variant = session.execute(
                select(ProductVariantModel).where(
                    ProductVariantModel.client_id == user.client_id,
                    ProductVariantModel.variant_id == requested_variant_id,
                )
            ).scalar_one_or_none()
            _require(variant is not None, message="Variant not found", code="VARIANT_NOT_FOUND", status_code=404)
            return session.execute(
                select(ProductModel).where(
                    ProductModel.client_id == user.client_id,
                    ProductModel.product_id == variant.product_id,
                )
            ).scalar_one()

        sku_root = str(identity.get("sku_root", "") or "").strip()
        if sku_root:
            return session.execute(
                select(ProductModel).where(
                    ProductModel.client_id == user.client_id,
                    ProductModel.sku_root == sku_root,
                )
            ).scalar_one_or_none()
        return None

    def _apply_receive_product_identity(
        self,
        session: Session,
        user: AuthenticatedUser,
        *,
        product: ProductModel | None,
        identity: dict[str, Any],
        update_matched_product_details: bool,
    ) -> tuple[ProductModel, str | None, bool]:
        default_price, min_price, derived_discount = self._normalize_product_pricing(identity)
        requested_supplier_id = self._ensure_supplier(session, user.client_id, str(identity.get("supplier", "")))
        requested_category_id = self._ensure_category(session, user.client_id, str(identity.get("category", "")))
        is_new_product = product is None

        if product is None:
            product = ProductModel(
                product_id=new_uuid(),
                client_id=user.client_id,
                slug=build_product_slug(str(identity["product_name"])),
            )
            session.add(product)

        purchase_supplier_id = requested_supplier_id or product.supplier_id

        if is_new_product or update_matched_product_details:
            product.category_id = requested_category_id
            product.supplier_id = purchase_supplier_id
            product.name = str(identity["product_name"]).strip()
            product.slug = build_product_slug(product.name)
            product.sku_root = str(identity.get("sku_root", "")).strip()
            product.brand = str(identity.get("brand", "")).strip()
            product.description = str(identity.get("description", "")).strip()
            product.status = "active"
            product.default_price_amount = default_price
            product.min_price_amount = min_price
            product.max_discount_percent = derived_discount
        session.flush()
        if is_new_product or update_matched_product_details:
            self._apply_product_media_instructions(session, user=user, product=product, identity=identity)
        return product, purchase_supplier_id, is_new_product

    def _prepare_receive_variant(
        self,
        session: Session,
        user: AuthenticatedUser,
        *,
        product: ProductModel,
        line: dict[str, Any],
        variants_by_id: dict[str, ProductVariantModel],
        variants_by_sku: dict[str, ProductVariantModel],
        variants_by_signature: dict[str, ProductVariantModel],
        update_matched_product_details: bool,
    ) -> tuple[ProductVariantModel, Decimal | None, Decimal, bool]:
        requested_variant_id = str(line.get("variant_id", "") or "").strip()
        requested_sku = str(line.get("sku", "") or "").strip()
        size = str(line.get("size", "")).strip()
        color = str(line.get("color", "")).strip()
        other = str(line.get("other", "")).strip()
        signature = build_variant_signature(size, color, other)
        quantity = as_decimal(line.get("quantity"))
        cost_amount, price_amount, variant_min_price = self._normalize_variant_pricing(line)

        variant = None
        is_new_variant = False
        if requested_variant_id:
            variant = variants_by_id.get(requested_variant_id)
            _require(variant is not None, message="Variant not found", code="VARIANT_NOT_FOUND", status_code=404)
        elif requested_sku and requested_sku in variants_by_sku:
            variant = variants_by_sku[requested_sku]
        elif signature and signature in variants_by_signature:
            variant = variants_by_signature[signature]

        if variant is not None:
            _require(
                str(variant.product_id) == str(product.product_id),
                message="Variant belongs to a different product",
                code="DUPLICATE_SKU",
            )
            receipt_cost = cost_amount if cost_amount is not None else as_optional_decimal(variant.cost_amount)
            if update_matched_product_details and price_amount is not None:
                variant.price_amount = price_amount
            if update_matched_product_details and variant_min_price is not None:
                variant.min_price_amount = variant_min_price
            if update_matched_product_details and line.get("reorder_level") not in ("", None):
                variant.reorder_level = as_decimal(line.get("reorder_level"))
            session.flush()
            return variant, receipt_cost, quantity, False

        variant = ProductVariantModel(
            variant_id=new_uuid(),
            client_id=user.client_id,
            product_id=product.product_id,
        )
        session.add(variant)
        variant.title = build_variant_title(size, color, other)
        final_sku = requested_sku or self._generate_unique_sku(
            session,
            user.client_id,
            product_name=product.name,
            sku_root=product.sku_root,
            size=size,
            color=color,
            other=other,
            exclude_variant_id=str(variant.variant_id),
        )
        if requested_sku and requested_sku in variants_by_sku:
            raise ApiException(status_code=400, code="DUPLICATE_SKU", message="Variant SKU already exists")
        variant.sku = final_sku
        variant.option_values_json = {"size": size, "color": color, "other": other}
        variant.status = "active"
        variant.cost_amount = cost_amount
        variant.price_amount = price_amount
        variant.min_price_amount = variant_min_price
        variant.reorder_level = as_decimal(line.get("reorder_level"))
        session.flush()
        variants_by_id[str(variant.variant_id)] = variant
        variants_by_sku[str(variant.sku)] = variant
        variants_by_signature[signature] = variant
        is_new_variant = True
        return variant, cost_amount, quantity, is_new_variant

    def receive_stock(
        self,
        user: AuthenticatedUser,
        *,
        action: str,
        location_id: str | None,
        source_purchase_order_id: str | None,
        notes: str,
        update_matched_product_details: bool,
        identity: dict[str, Any],
        lines: list[dict[str, Any]],
    ) -> dict[str, Any]:
        _require_page(user, "Inventory")
        if action == "save_template_only":
            _require(
                self._can_save_template_only(user),
                message="Only owners or super admins can save catalog templates without stock",
                code="ACCESS_DENIED",
                status_code=403,
            )
        with self._session_factory() as session:
            location_context = self._location_context(session, user.client_id, location_id)
            source_purchase: PurchaseModel | None = None
            if source_purchase_order_id:
                source_purchase = session.execute(
                    select(PurchaseModel).where(
                        PurchaseModel.client_id == user.client_id,
                        PurchaseModel.purchase_id == source_purchase_order_id,
                    )
                ).scalar_one_or_none()
                _require(
                    source_purchase is not None,
                    message="Source purchase order not found",
                    code="NOT_FOUND",
                    status_code=404,
                )
                _require(
                    source_purchase.status == "draft",
                    message="Only draft purchase orders can be linked for receiving",
                    code="INVALID_REQUEST",
                    status_code=400,
                )
            product = self._resolve_receive_product(session, user, identity, lines)
            product, purchase_supplier_id, is_new_product = self._apply_receive_product_identity(
                session,
                user,
                product=product,
                identity=identity,
                update_matched_product_details=update_matched_product_details,
            )

            existing_variants = list(
                session.execute(
                    select(ProductVariantModel).where(
                        ProductVariantModel.client_id == user.client_id,
                        ProductVariantModel.product_id == product.product_id,
                    )
                ).scalars()
            )
            variants_by_id = {str(item.variant_id): item for item in existing_variants}
            variants_by_sku = {str(item.sku): item for item in existing_variants}
            variants_by_signature = {
                build_variant_signature(
                    option_value(item.option_values_json, "size"),
                    option_value(item.option_values_json, "color"),
                    option_value(item.option_values_json, "other"),
                ): item
                for item in existing_variants
            }

            prepared_lines: list[tuple[ProductVariantModel, Decimal | None, Decimal, bool]] = []
            seen_variant_ids: set[str] = set()
            for line in lines:
                variant, receipt_cost, quantity, is_new_variant = self._prepare_receive_variant(
                    session,
                    user,
                    product=product,
                    line=line,
                    variants_by_id=variants_by_id,
                    variants_by_sku=variants_by_sku,
                    variants_by_signature=variants_by_signature,
                    update_matched_product_details=update_matched_product_details,
                )
                variant_key = str(variant.variant_id)
                _require(
                    variant_key not in seen_variant_ids,
                    message="Each receipt line must target a unique variant",
                    code="DUPLICATE_VARIANT_LINE",
                )
                if action == "receive_stock":
                    _require(receipt_cost is not None, message="Purchase cost is required to receive stock")
                seen_variant_ids.add(variant_key)
                prepared_lines.append((variant, receipt_cost, quantity, is_new_variant))

            if action == "save_template_only":
                _require(
                    is_new_product or any(is_new_variant for _variant, _cost, _quantity, is_new_variant in prepared_lines),
                    message="Template save requires a new product or at least one new variant",
                    code="NOTHING_TO_SAVE",
                )
                session.commit()
                product_payload = self._product_payload(
                    session,
                    user.client_id,
                    str(product.product_id),
                    location_context.active_location_id,
                )
                variant_map = {item["variant_id"]: item for item in product_payload["variants"]}
                return {
                    "action": action,
                    "purchase_id": None,
                    "purchase_number": None,
                    "product": product_payload,
                    "lines": [
                        {
                            "quantity_received": ZERO,
                            "variant": variant_map[str(variant.variant_id)],
                        }
                        for variant, _receipt_cost, _quantity, _is_new_variant in prepared_lines
                    ],
                }

            settings = self._client_settings(session, user.client_id)
            prefix = settings.purchase_prefix if settings else "PO"
            subtotal = sum(quantity * as_decimal(receipt_cost) for _variant, receipt_cost, quantity, _is_new_variant in prepared_lines)
            purchase = PurchaseModel(
                purchase_id=new_uuid(),
                client_id=user.client_id,
                supplier_id=purchase_supplier_id,
                location_id=location_context.active_location_id,
                purchase_number=_new_number(prefix),
                status="received",
                ordered_at=now_utc(),
                received_at=now_utc(),
                notes=notes.strip(),
                created_by_user_id=user.user_id,
                subtotal_amount=subtotal,
                total_amount=subtotal,
            )
            if source_purchase is not None:
                po_note = f"Linked source purchase order: {source_purchase.purchase_number}"
                purchase.notes = f"{purchase.notes}\n{po_note}".strip()
            session.add(purchase)
            session.flush()

            response_lines: list[dict[str, Any]] = []
            for variant, receipt_cost, quantity, _is_new_variant in prepared_lines:
                effective_price = self._effective_variant_price(product, variant)
                purchase_item = PurchaseItemModel(
                    purchase_item_id=new_uuid(),
                    client_id=user.client_id,
                    purchase_id=purchase.purchase_id,
                    variant_id=variant.variant_id,
                    quantity=quantity,
                    received_quantity=quantity,
                    unit_cost_amount=as_decimal(receipt_cost),
                    line_total_amount=quantity * as_decimal(receipt_cost),
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
                        unit_cost_amount=as_decimal(receipt_cost),
                        unit_price_amount=effective_price,
                        reason=notes.strip() or "Stock received",
                        created_by_user_id=user.user_id,
                    )
                )
                response_lines.append(
                    {
                        "variant_id": str(variant.variant_id),
                        "quantity_received": quantity,
                    }
                )
            session.commit()

            product_payload = self._product_payload(
                session,
                user.client_id,
                str(product.product_id),
                location_context.active_location_id,
            )
            variant_map = {item["variant_id"]: item for item in product_payload["variants"]}
            return {
                "action": action,
                "purchase_id": str(purchase.purchase_id),
                "purchase_number": purchase.purchase_number,
                "product": product_payload,
                "lines": [
                    {
                        "quantity_received": line["quantity_received"],
                        "variant": variant_map[line["variant_id"]],
                    }
                    for line in response_lines
                ],
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
            effective_price = self._effective_variant_price(product, variant)
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
                    unit_cost_amount=as_optional_decimal(variant.cost_amount),
                    unit_price_amount=effective_price,
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
                "supplier": supplier.name if supplier else "",
                "category": category.name if category else "",
                "location_id": location_context.active_location_id,
                "location_name": location_context.active_location_name,
                "unit_cost": as_optional_decimal(variant.cost_amount),
                "unit_price": effective_price,
                "reorder_level": threshold,
                "on_hand": refreshed_on_hand,
                "reserved": refreshed_reserved,
                "available_to_sell": refreshed_available,
                "low_stock": threshold > ZERO and refreshed_available <= threshold,
            }

    def update_inline_fields(
        self,
        user: AuthenticatedUser,
        *,
        variant_id: str,
        supplier: str | None,
        reorder_level: Decimal | None,
    ) -> dict[str, Any]:
        _require_page(user, "Inventory")
        _require(
            supplier is not None or reorder_level is not None,
            message="At least one field must be provided for inline update",
        )
        if reorder_level is not None:
            _require(reorder_level >= ZERO, message="Reorder level cannot be negative")

        with self._session_factory() as session:
            location_context = self._location_context(session, user.client_id, None)
            variant_row = session.execute(
                self._base_variant_stmt(user.client_id).where(ProductVariantModel.variant_id == variant_id)
            ).first()
            _require(variant_row is not None, message="Variant not found", code="VARIANT_NOT_FOUND", status_code=404)
            product, variant, _supplier, _category = variant_row

            if supplier is not None:
                product.supplier_id = self._ensure_supplier(session, user.client_id, supplier)
            if reorder_level is not None:
                variant.reorder_level = reorder_level
            session.commit()

            on_hand_map, reserved_map = self._stock_maps(session, user.client_id, location_context.active_location_id)
            refreshed_variant_row = session.execute(
                self._base_variant_stmt(user.client_id).where(ProductVariantModel.variant_id == variant_id)
            ).first()
            _require(refreshed_variant_row is not None, message="Variant not found", code="VARIANT_NOT_FOUND", status_code=404)
            refreshed_product, refreshed_variant, refreshed_supplier, refreshed_category = refreshed_variant_row
            on_hand = on_hand_map.get(str(refreshed_variant.variant_id), ZERO)
            reserved = reserved_map.get(str(refreshed_variant.variant_id), ZERO)
            available = on_hand - reserved
            threshold = as_decimal(refreshed_variant.reorder_level)

            return {
                "variant_id": str(refreshed_variant.variant_id),
                "product_id": str(refreshed_product.product_id),
                "product_name": refreshed_product.name,
                "label": build_variant_label(refreshed_product.name, refreshed_variant.title),
                "sku": refreshed_variant.sku,
                "supplier": refreshed_supplier.name if refreshed_supplier else "",
                "category": refreshed_category.name if refreshed_category else "",
                "location_id": location_context.active_location_id,
                "location_name": location_context.active_location_name,
                "unit_cost": as_optional_decimal(refreshed_variant.cost_amount),
                "unit_price": self._effective_variant_price(refreshed_product, refreshed_variant),
                "reorder_level": threshold,
                "on_hand": on_hand,
                "reserved": reserved,
                "available_to_sell": available,
                "low_stock": threshold > ZERO and available <= threshold,
            }


    def list_purchase_orders(self, user: AuthenticatedUser, *, status: str | None = None, query: str = '') -> list[dict[str, Any]]:
        _require_page(user, "Purchases")
        with self._session_factory() as session:
            stmt = select(PurchaseModel).where(PurchaseModel.client_id == user.client_id)
            if status:
                stmt = stmt.where(PurchaseModel.status == status)
            if query:
                search_term = f"%{query}%"
                stmt = stmt.where(
                    or_(
                        PurchaseModel.purchase_number.ilike(search_term),
                        PurchaseModel.notes.ilike(search_term),
                    )
                )
            stmt = stmt.order_by(PurchaseModel.created_at.desc())
            purchases = session.execute(stmt).scalars().all()
            return [
                {
                    "purchase_id": str(purchase.purchase_id),
                    "purchase_no": purchase.purchase_number,
                    "purchase_date": purchase.ordered_at.isoformat() if purchase.ordered_at else "",
                    "supplier_id": str(purchase.supplier_id) if purchase.supplier_id else "",
                    "supplier_name": self._get_supplier_name(session, purchase.supplier_id) if purchase.supplier_id else "",
                    "reference_no": self._purchase_reference_no(purchase),
                    "subtotal": purchase.subtotal_amount,
                    "status": purchase.status,
                    "created_at": purchase.created_at.isoformat() if purchase.created_at else "",
                }
                for purchase in purchases
            ]

    def get_purchase_order(self, user: AuthenticatedUser, purchase_order_id: str) -> dict[str, Any]:
        _require_page(user, "Purchases")
        with self._session_factory() as session:
            purchase = session.execute(
                select(PurchaseModel).where(
                    PurchaseModel.client_id == user.client_id,
                    PurchaseModel.purchase_id == purchase_order_id,
                )
            ).scalar_one_or_none()
            _require(purchase is not None, message="Purchase order not found", code="NOT_FOUND", status_code=404)

            # Get purchase items
            purchase_items = session.execute(
                select(PurchaseItemModel).where(PurchaseItemModel.purchase_id == purchase.purchase_id)
            ).scalars().all()

            # Get supplier name
            supplier_name = self._get_supplier_name(session, purchase.supplier_id) if purchase.supplier_id else ""

            return {
                "purchase_id": str(purchase.purchase_id),
                "purchase_no": purchase.purchase_number,
                "purchase_date": purchase.ordered_at.isoformat() if purchase.ordered_at else "",
                "supplier_id": str(purchase.supplier_id) if purchase.supplier_id else "",
                "supplier_name": supplier_name,
                "reference_no": self._purchase_reference_no(purchase),
                "note": purchase.notes,
                "subtotal": purchase.subtotal_amount,
                "status": purchase.status,
                "created_at": purchase.created_at.isoformat() if purchase.created_at else "",
                "created_by_user_id": str(purchase.created_by_user_id) if purchase.created_by_user_id else "",
                "lines": [
                    {
                        "line_id": str(item.purchase_item_id),
                        "variant_id": str(item.variant_id),
                        "product_id": str(item.variant.product_id) if item.variant else "",
                        "product_name": item.variant.product.name if item.variant and item.variant.product else "",
                        "qty": item.quantity,
                        "unit_cost": item.unit_cost_amount,
                        "line_total": item.line_total_amount,
                    }
                    for item in purchase_items
                ],
            }

    def lookup_purchase_variants(self, user: AuthenticatedUser, *, query: str, location_id: str | None = None) -> list[dict[str, Any]]:
        _require_page(user, "Purchases")
        trimmed = query.strip()
        if not trimmed:
            return []

        with self._session_factory() as session:
            location_context = self._location_context(session, user.client_id, location_id)
            rows = session.execute(self._apply_variant_search(self._base_variant_stmt(user.client_id), trimmed)).all()
            on_hand_map, reserved_map = self._stock_maps(session, user.client_id, location_context.active_location_id)
            results = []
            for product, variant, supplier, category in rows:
                if product.status != "active" or variant.status != "active":
                    continue
                on_hand = on_hand_map.get(str(variant.variant_id), ZERO)
                reserved = reserved_map.get(str(variant.variant_id), ZERO)
                available = on_hand - reserved
                results.append(
                    {
                        "variant_id": str(variant.variant_id),
                        "product_id": str(product.product_id),
                        "label": build_variant_label(product.name, variant.title),
                        "current_stock": available,
                        "default_purchase_price": as_optional_decimal(variant.cost_amount),
                        "sku": variant.sku,
                    }
                )
            return results

    def lookup_purchase_suppliers(self, user: AuthenticatedUser, *, query: str) -> list[dict[str, Any]]:
        _require_page(user, "Purchases")
        trimmed = query.strip()
        if not trimmed:
            return []

        with self._session_factory() as session:
            search_term = f"%{trimmed}%"
            suppliers = session.execute(
                select(SupplierModel)
                .where(
                    SupplierModel.client_id == user.client_id,
                    SupplierModel.name.ilike(search_term),
                )
                .limit(20)
            ).scalars().all()
            return [
                {
                    "supplier_id": str(supplier.supplier_id),
                    "name": supplier.name,
                }
                for supplier in suppliers
            ]

    def create_purchase_order(
        self,
        user: AuthenticatedUser,
        *,
        purchase_date: str,
        supplier_id: str,
        reference_no: str,
        note: str,
        payment_status: str,
        lines: list[dict],
    ) -> dict[str, Any]:
        _require_page(user, "Purchases")
        with self._session_factory() as session:
            # Validate supplier exists
            supplier = session.execute(
                select(SupplierModel).where(
                    SupplierModel.client_id == user.client_id,
                    SupplierModel.supplier_id == supplier_id,
                )
            ).scalar_one_or_none()
            _require(supplier is not None, message="Supplier not found", code="NOT_FOUND", status_code=404)

            # Validate lines
            _require(lines, message="At least one line is required", code="INVALID_REQUEST", status_code=400)

            # Process each line to validate variant and calculate totals
            processed_lines = []
            subtotal = ZERO
            for line in lines:
                variant_id = str(line.get("variant_id", "")).strip()
                qty = as_decimal(line.get("qty"))
                unit_cost = as_decimal(line.get("unit_cost"))

                _require(variant_id, message="Variant ID is required", code="INVALID_REQUEST", status_code=400)
                _require(qty is not None and qty > ZERO, message="Quantity must be greater than zero", code="INVALID_REQUEST", status_code=400)
                _require(unit_cost is not None and unit_cost >= ZERO, message="Unit cost must be greater than or equal to zero", code="INVALID_REQUEST", status_code=400)

                variant = session.execute(
                    select(ProductVariantModel).where(
                        ProductVariantModel.client_id == user.client_id,
                        ProductVariantModel.variant_id == variant_id,
                    )
                ).scalar_one_or_none()
                _require(variant is not None, message="Variant not found", code="NOT_FOUND", status_code=404)

                line_total = qty * unit_cost
                subtotal += line_total

                processed_lines.append({
                    "variant_id": variant_id,
                    "quantity": qty,
                    "unit_cost": unit_cost,
                    "line_total": line_total,
                })

            # Create purchase order
            settings = self._client_settings(session, user.client_id)
            prefix = settings.purchase_prefix if settings else "PO"
            purchase_number = self._new_number(prefix)

            purchase = PurchaseModel(
                purchase_id=new_uuid(),
                client_id=user.client_id,
                supplier_id=supplier_id,
                location_id=self._get_default_location_id(session, user.client_id),  # Use default location
                purchase_number=purchase_number,
                status="draft",  # Start as draft
                ordered_at=datetime.fromisoformat(purchase_date.replace("Z", "+00:00")) if purchase_date else None,
                received_at=None,
                notes=note.strip(),
                created_by_user_id=user.user_id,
                subtotal_amount=subtotal,
                total_amount=subtotal,
            )
            session.add(purchase)
            session.flush()

            # Create purchase items
            for line in processed_lines:
                purchase_item = PurchaseItemModel(
                    purchase_item_id=new_uuid(),
                    client_id=user.client_id,
                    purchase_id=purchase.purchase_id,
                    variant_id=line["variant_id"],
                    quantity=line["quantity"],
                    received_quantity=ZERO,  # Initially nothing received
                    unit_cost_amount=line["unit_cost"],
                    line_total_amount=line["line_total"],
                    notes="",
                )
                session.add(purchase_item)

            session.commit()

            return self.get_purchase_order(user, str(purchase.purchase_id))

    def update_purchase_order(
        self,
        user: AuthenticatedUser,
        *,
        purchase_order_id: str,
        purchase_date: str | None = None,
        supplier_id: str | None = None,
        reference_no: str | None = None,
        note: str | None = None,
        payment_status: str | None = None,
        lines: list[dict] | None = None,
    ) -> dict[str, Any]:
        _require_page(user, "Purchases")
        with self._session_factory() as session:
            purchase = session.execute(
                select(PurchaseModel).where(
                    PurchaseModel.client_id == user.client_id,
                    PurchaseModel.purchase_id == purchase_order_id,
                )
            ).scalar_one_or_none()
            _require(purchase is not None, message="Purchase order not found", code="NOT_FOUND", status_code=404)

            # Only allow updates on draft or cancelled orders
            _require(purchase.status in ["draft", "cancelled"], message="Can only update draft or cancelled purchase orders", code="INVALID_REQUEST", status_code=400)

            # Update fields if provided
            if purchase_date is not None:
                purchase.ordered_at = datetime.fromisoformat(purchase_date.replace("Z", "+00:00")) if purchase_date else None
            if supplier_id is not None:
                # Validate supplier exists
                supplier = session.execute(
                    select(SupplierModel).where(
                        SupplierModel.client_id == user.client_id,
                        SupplierModel.supplier_id == supplier_id,
                    )
                ).scalar_one_or_none()
                _require(supplier is not None, message="Supplier not found", code="NOT_FOUND", status_code=404)
                purchase.supplier_id = supplier_id
            if reference_no is not None:
                if hasattr(purchase, "reference_no"):
                    purchase.reference_no = reference_no
            if note is not None:
                purchase.notes = note.strip()
            if payment_status is not None:
                # For now, we don't store payment_status separately, but we could add it to the model
                pass

            # Update lines if provided
            if lines is not None:
                _require(lines, message="At least one line is required", code="INVALID_REQUEST", status_code=400)

                # Delete existing purchase items
                session.execute(
                    delete(PurchaseItemModel).where(PurchaseItemModel.purchase_id == purchase.purchase_id)
                )

                # Process new lines
                processed_lines = []
                subtotal = ZERO
                for line in lines:
                    variant_id = str(line.get("variant_id", "")).strip()
                    qty = as_decimal(line.get("qty"))
                    unit_cost = as_decimal(line.get("unit_cost"))

                    _require(variant_id, message="Variant ID is required", code="INVALID_REQUEST", status_code=400)
                    _require(qty is not None and qty > ZERO, message="Quantity must be greater than zero", code="INVALID_REQUEST", status_code=400)
                    _require(unit_cost is not None and unit_cost >= ZERO, message="Unit cost must be greater than or equal to zero", code="INVALID_REQUEST", status_code=400)

                    variant = session.execute(
                        select(ProductVariantModel).where(
                            ProductVariantModel.client_id == user.client_id,
                            ProductVariantModel.variant_id == variant_id,
                        )
                ).scalar_one_or_none()
                _require(variant is not None, message="Variant not found", code="NOT_FOUND", status_code=404)

                line_total = qty * unit_cost
                subtotal += line_total

                processed_lines.append({
                    "variant_id": variant_id,
                    "quantity": qty,
                    "unit_cost": unit_cost,
                    "line_total": line_total,
                })

                # Create new purchase items
                for line in processed_lines:
                    purchase_item = PurchaseItemModel(
                        purchase_item_id=new_uuid(),
                        client_id=user.client_id,
                        purchase_id=purchase.purchase_id,
                        variant_id=line["variant_id"],
                        quantity=line["quantity"],
                        received_quantity=ZERO,  # Reset received quantity when lines change
                        unit_cost_amount=line["unit_cost"],
                        line_total_amount=line["line_total"],
                        notes="",
                    )
                    session.add(purchase_item)

                purchase.subtotal_amount = subtotal
                purchase.total_amount = subtotal

            session.commit()
            return self.get_purchase_order(user, purchase_order_id)

    def receive_purchase_order(self, user: AuthenticatedUser, *, purchase_order_id: str) -> dict[str, Any]:
        _require_page(user, "Purchases")
        with self._session_factory() as session:
            purchase = session.execute(
                select(PurchaseModel).where(
                    PurchaseModel.client_id == user.client_id,
                    PurchaseModel.purchase_id == purchase_order_id,
                )
            ).scalar_one_or_none()
            _require(purchase is not None, message="Purchase order not found", code="NOT_FOUND", status_code=404)

            # Only allow receiving draft orders
            _require(purchase.status == "draft", message="Can only receive draft purchase orders", code="INVALID_REQUEST", status_code=400)

            # Get purchase items to build lines for receive_stock
            purchase_items = session.execute(
                select(PurchaseItemModel).where(PurchaseItemModel.purchase_id == purchase.purchase_id)
            ).scalars().all()

            _require(purchase_items, message="Purchase order has no items", code="INVALID_REQUEST", status_code=400)

            # Build lines for receive_stock
            lines = []
            for item in purchase_items:
                lines.append({
                    "variant_id": str(item.variant_id),
                    "quantity": item.quantity,
                    "default_purchase_price": item.unit_cost_amount,
                })

            # Use receive_stock to process the receipt
            result = self.receive_stock(
                user,
                action="receive_stock",
                location_id=None,  # Use purchase's location or default
                source_purchase_order_id=str(purchase.purchase_id),
                notes=purchase.notes or "Received via purchase order",
                update_matched_product_details=False,
                identity={
                    "product_name": "Purchase Order Receipt",  # Dummy, not used when variant_id provided
                    "sku_root": "",
                },
                lines=lines,
            )

            # Update purchase status to received
            purchase.status = "received"
            purchase.received_at = now_utc()
            session.add(purchase)
            session.commit()

            return self.get_purchase_order(user, purchase_order_id)

    def cancel_purchase_order(self, user: AuthenticatedUser, *, purchase_order_id: str, notes: str = "") -> dict[str, Any]:
        _require_page(user, "Purchases")
        with self._session_factory() as session:
            purchase = session.execute(
                select(PurchaseModel).where(
                    PurchaseModel.client_id == user.client_id,
                    PurchaseModel.purchase_id == purchase_order_id,
                )
            ).scalar_one_or_none()
            _require(purchase is not None, message="Purchase order not found", code="NOT_FOUND", status_code=404)

            # Only allow cancelling draft orders
            _require(purchase.status == "draft", message="Can only cancel draft purchase orders", code="INVALID_REQUEST", status_code=400)

            # Update status to cancelled
            purchase.status = "cancelled"
            if notes:
                purchase.notes = f"{purchase.notes}\nCancelled: {notes}".strip()
            session.add(purchase)
            session.commit()

            return self.get_purchase_order(user, purchase_order_id)

    # Helper methods
    def _get_supplier_name(self, session: Session, supplier_id: str | None) -> str:
        if not supplier_id:
            return ""
        supplier = session.execute(
            select(SupplierModel.name).where(SupplierModel.supplier_id == supplier_id)
        ).scalar_one_or_none()
        return supplier or ""

    def _purchase_reference_no(self, purchase: PurchaseModel) -> str:
        return str(getattr(purchase, "reference_no", "") or "")

    def _get_default_location_id(self, session: Session, client_id: str) -> str:
        location = session.execute(
            select(LocationModel.location_id)
            .where(LocationModel.client_id == client_id)
            .limit(1)
        ).scalar_one_or_none()
        _require(location is not None, message="No location found for client", code="INTERNAL_ERROR", status_code=500)
        return location
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
                effective_price = self._effective_variant_price(product, variant)
                if effective_price is None or effective_price <= ZERO:
                    continue
                items.append(
                    {
                        "variant_id": str(variant.variant_id),
                        "product_id": str(product.product_id),
                        "product_name": product.name,
                        "label": build_variant_label(product.name, variant.title),
                        "sku": variant.sku,
                        "available_to_sell": available,
                        "unit_price": effective_price,
                        "min_price": self._effective_variant_min_price(product, variant),
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
            row = session.execute(
                select(ProductVariantModel, ProductModel)
                .join(ProductModel, ProductModel.product_id == ProductVariantModel.product_id)
                .where(
                    ProductVariantModel.client_id == user.client_id,
                    ProductVariantModel.variant_id == line["variant_id"],
                    ProductVariantModel.status == "active",
                )
            ).first()
            _require(row is not None, message="Variant not found", code="VARIANT_NOT_FOUND", status_code=404)
            variant, product = row
            quantity = as_decimal(line["quantity"])
            discount_amount = as_decimal(line.get("discount_amount"))
            input_unit_price = as_optional_decimal(line.get("unit_price"))
            unit_price = input_unit_price if input_unit_price is not None else self._effective_variant_price(product, variant)
            _require(
                unit_price is not None and unit_price > ZERO,
                message="Variant must have a selling price before it can be sold",
                code="PRICE_REQUIRED",
            )
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
        self._validate_order_pricing(session, user, order)

        if action in {"confirm", "confirm_and_fulfill"}:
            order.status = "confirmed"
            order.confirmed_at = now_utc()
            self._validate_available_stock(session, user, order)
        if action == "confirm_and_fulfill":
            self._fulfill_order(session, user, order)
        return order

    def _validate_order_pricing(self, session: Session, user: AuthenticatedUser, order: SalesOrderModel) -> None:
        for item, variant, product in session.execute(
            select(SalesOrderItemModel, ProductVariantModel, ProductModel)
            .join(ProductVariantModel, ProductVariantModel.variant_id == SalesOrderItemModel.variant_id)
            .join(ProductModel, ProductModel.product_id == ProductVariantModel.product_id)
            .where(
                SalesOrderItemModel.client_id == user.client_id,
                SalesOrderItemModel.sales_order_id == order.sales_order_id,
            )
        ).all():
            quantity = as_decimal(item.quantity)
            line_total = as_decimal(item.line_total_amount)
            effective_price = self._effective_variant_price(product, variant)
            _require(
                effective_price is not None and effective_price > ZERO,
                message="Variant must have a selling price before it can be sold",
                code="PRICE_REQUIRED",
            )
            min_price = self._effective_variant_min_price(product, variant)
            if min_price is not None:
                _require(
                    line_total >= quantity * min_price,
                    message="Line price is below the minimum selling price",
                    code="MIN_PRICE_VIOLATION",
                )

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
                    unit_cost_amount=as_optional_decimal(variant.cost_amount),
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
        customer_name = ""
        if order.customer_id:
            customer = session.execute(
                select(CustomerModel).where(
                    CustomerModel.client_id == user.client_id,
                    CustomerModel.customer_id == order.customer_id,
                )
            ).scalar_one_or_none()
            customer_name = customer.name if customer else ""
        self._finance_posting.post_sale_fulfillment(
            session,
            user=user,
            order=order,
            customer_name=customer_name,
        )

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
            self._validate_order_pricing(session, user, order)
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

    def record_order_payment(
        self,
        user: AuthenticatedUser,
        *,
        sales_order_id: str,
        payment_date: str,
        amount: Decimal,
        method: str,
        reference: str,
        note: str,
    ) -> dict[str, Any]:
        _require_page(user, "Sales")
        with self._session_factory() as session:
            order = session.execute(
                select(SalesOrderModel).where(
                    SalesOrderModel.client_id == user.client_id,
                    SalesOrderModel.sales_order_id == sales_order_id,
                )
            ).scalar_one_or_none()
            _require(order is not None, message="Order not found", code="ORDER_NOT_FOUND", status_code=404)
            amount_decimal = as_decimal(amount)
            _require(amount_decimal > ZERO, message="Payment amount must be greater than zero")
            outstanding = max(ZERO, as_decimal(order.total_amount) - as_decimal(order.paid_amount))
            _require(outstanding > ZERO, message="Order is already fully paid")
            _require(amount_decimal <= outstanding, message="Payment amount exceeds outstanding balance")
            payment = PaymentModel(
                payment_id=new_uuid(),
                client_id=user.client_id,
                sales_order_id=order.sales_order_id,
                status="completed",
                direction="in",
                method=method.strip() or "manual",
                amount=amount_decimal,
                paid_at=datetime.fromisoformat(payment_date.replace("Z", "+00:00")),
                reference=reference.strip(),
                notes=note.strip(),
                created_by_user_id=user.user_id,
            )
            session.add(payment)
            order.paid_amount = as_decimal(order.paid_amount) + amount_decimal
            if order.paid_amount >= as_decimal(order.total_amount):
                order.payment_status = "paid"
            elif order.paid_amount > ZERO:
                order.payment_status = "partial"
            else:
                order.payment_status = "unpaid"
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


class CustomersService(CommerceBaseService):
    def list_workspace_customers(
        self,
        user: AuthenticatedUser,
        *,
        query: str = "",
        limit: int = 12,
    ) -> list[dict[str, Any]]:
        _require_page(user, "Customers")
        with self._session_factory() as session:
            stmt = select(CustomerModel).where(
                CustomerModel.client_id == user.client_id,
                CustomerModel.status == "active",
            )
            trimmed = query.strip()
            normalized_text = normalize_lookup_text(trimmed)
            normalized_phone = normalize_phone(trimmed)
            normalized_email = normalize_email(trimmed)
            if normalized_text:
                pattern = f"%{normalized_text}%"
                filters = [func.lower(CustomerModel.name).like(pattern)]
                if normalized_phone:
                    filters.append(CustomerModel.phone_normalized.like(f"{normalized_phone}%"))
                if normalized_email:
                    filters.append(CustomerModel.email_normalized.like(f"{normalized_email}%"))
                stmt = stmt.where(or_(*filters))

            customers = session.execute(
                stmt.order_by(CustomerModel.updated_at.desc(), CustomerModel.name.asc()).limit(limit)
            ).scalars().all()
            return [self._customer_workspace_payload(session, customer) for customer in customers]

    def _customer_workspace_payload(self, session: Session, customer: CustomerModel) -> dict[str, Any]:
        orders = session.execute(
            select(SalesOrderModel)
            .where(
                SalesOrderModel.client_id == customer.client_id,
                SalesOrderModel.customer_id == customer.customer_id,
            )
            .order_by(SalesOrderModel.created_at.desc())
        ).scalars().all()
        returns = session.execute(
            select(SalesReturnModel)
            .where(
                SalesReturnModel.client_id == customer.client_id,
                SalesReturnModel.customer_id == customer.customer_id,
            )
            .order_by(SalesReturnModel.created_at.desc())
        ).scalars().all()

        completed_orders = [order for order in orders if order.status == "completed"]
        open_orders = [order for order in orders if order.status in {"draft", "confirmed"}]
        lifetime_revenue = sum((as_decimal(order.total_amount) for order in completed_orders), ZERO)
        outstanding_balance = sum(
            (
                max(ZERO, as_decimal(order.total_amount) - as_decimal(order.paid_amount))
                for order in orders
                if order.status != "cancelled"
            ),
            ZERO,
        )

        recent_orders = [
            {
                "sales_order_id": str(order.sales_order_id),
                "order_number": order.order_number,
                "status": order.status,
                "payment_status": order.payment_status,
                "total_amount": as_decimal(order.total_amount),
                "ordered_at": order.ordered_at.isoformat() if order.ordered_at else None,
            }
            for order in orders[:3]
        ]

        recent_returns = []
        order_numbers: dict[str, str] = {}
        if returns:
            order_ids = [record.sales_order_id for record in returns if record.sales_order_id]
            if order_ids:
                order_numbers = {
                    str(order.sales_order_id): order.order_number
                    for order in session.execute(
                        select(SalesOrderModel).where(
                            SalesOrderModel.client_id == customer.client_id,
                            SalesOrderModel.sales_order_id.in_(order_ids),
                        )
                    ).scalars()
                }
            recent_returns = [
                {
                    "sales_return_id": str(record.sales_return_id),
                    "return_number": record.return_number,
                    "order_number": order_numbers.get(str(record.sales_order_id or ""), ""),
                    "refund_status": record.refund_status,
                    "refund_amount": as_decimal(record.refund_amount),
                    "requested_at": record.requested_at.isoformat() if record.requested_at else None,
                }
                for record in returns[:3]
            ]

        return {
            "customer_id": str(customer.customer_id),
            "name": customer.name,
            "phone": customer.phone,
            "email": customer.email,
            "address": customer.address,
            "total_orders": len(orders),
            "completed_orders": len(completed_orders),
            "open_orders": len(open_orders),
            "total_returns": len(returns),
            "lifetime_revenue": lifetime_revenue,
            "outstanding_balance": outstanding_balance,
            "last_order_at": orders[0].ordered_at.isoformat() if orders and orders[0].ordered_at else None,
            "last_return_at": returns[0].requested_at.isoformat() if returns and returns[0].requested_at else None,
            "recent_orders": recent_orders,
            "recent_returns": recent_returns,
        }


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
                            unit_cost_amount=as_optional_decimal(variant.cost_amount),
                            unit_price_amount=as_decimal(return_item.unit_refund_amount),
                            reason=str(line.get("reason", "")).strip() or "Return restocked",
                            created_by_user_id=user.user_id,
                        )
                    )

            return_record.subtotal_amount = subtotal
            return_record.refund_amount = refund_total
            session.commit()
            return self._return_payload(session, return_record)

    def get_return(self, user: AuthenticatedUser, return_id: str) -> dict[str, Any] | None:
        _require_page(user, "Returns")
        with self._session_factory() as session:
            stmt = select(SalesReturnModel).where(
                SalesReturnModel.client_id == user.client_id,
                SalesReturnModel.sales_return_id == return_id,
            )
            record = session.execute(stmt).scalar_one_or_none()
            if record is None:
                return None
            return self._return_payload(session, record)

    def update_return(
        self,
        user: AuthenticatedUser,
        return_id: str,
        payload: ReturnUpdateRequest | None,
    ) -> dict[str, Any] | None:
        _require_page(user, "Returns")
        with self._session_factory() as session:
            return_record = session.execute(
                select(SalesReturnModel).where(
                    SalesReturnModel.client_id == user.client_id,
                    SalesReturnModel.sales_return_id == return_id,
                )
            ).scalar_one_or_none()
            if return_record is None:
                return None

            # Update fields if provided
            if payload is not None:
                if payload.refund_status is not None:
                    return_record.refund_status = payload.refund_status
                if payload.notes is not None:
                    return_record.notes = payload.notes.strip()
                if payload.status is not None:
                    return_record.status = payload.status

            session.add(return_record)
            session.commit()
            return self._return_payload(session, return_record)

    def record_refund_payment(
        self,
        user: AuthenticatedUser,
        *,
        return_id: str,
        refund_date: str,
        amount: Decimal,
        method: str,
        reference: str,
        note: str,
    ) -> dict[str, Any] | None:
        _require_page(user, "Returns")
        with self._session_factory() as session:
            return_record = session.execute(
                select(SalesReturnModel).where(
                    SalesReturnModel.client_id == user.client_id,
                    SalesReturnModel.sales_return_id == return_id,
                )
            ).scalar_one_or_none()
            if return_record is None:
                return None
            refund_amount = as_decimal(amount)
            _require(refund_amount > ZERO, message="Refund amount must be greater than zero")
            refunded_total = self._finance_posting.refunded_total(
                session,
                client_id=user.client_id,
                sales_return_id=str(return_record.sales_return_id),
            )
            outstanding = max(ZERO, as_decimal(return_record.refund_amount) - refunded_total)
            _require(outstanding > ZERO, message="Return is already fully refunded")
            _require(refund_amount <= outstanding, message="Refund amount exceeds outstanding refund")

            customer_name = ""
            if return_record.customer_id:
                customer = session.execute(
                    select(CustomerModel).where(
                        CustomerModel.client_id == user.client_id,
                        CustomerModel.customer_id == return_record.customer_id,
                    )
                ).scalar_one_or_none()
                customer_name = customer.name if customer else ""

            occurred_at = datetime.fromisoformat(refund_date.replace("Z", "+00:00"))
            self._finance_posting.record_return_refund(
                session,
                user=user,
                return_record=return_record,
                customer_name=customer_name,
                amount=refund_amount,
                occurred_at=occurred_at,
                method=method,
                reference=reference,
                note=note,
            )
            next_refunded_total = refunded_total + refund_amount
            if next_refunded_total >= as_decimal(return_record.refund_amount):
                return_record.refund_status = "paid"
            elif next_refunded_total > ZERO:
                return_record.refund_status = "partial"
            else:
                return_record.refund_status = "pending"
            session.add(return_record)
            session.commit()
            return self._return_payload(session, return_record)
