from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, JSON, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from easy_ecom.data.store.postgres_db import Base
from easy_ecom.data.store.sql_types import GUID


Amount = Numeric(12, 2)
Percent = Numeric(5, 2)
Quantity = Numeric(14, 3)
Timestamp = DateTime(timezone=True)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        Timestamp,
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        Timestamp,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class TenantMixin:
    client_id: Mapped[str] = mapped_column(
        GUID(),
        ForeignKey("clients.client_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )


class ClientModel(TimestampMixin, Base):
    __tablename__ = "clients"

    client_id: Mapped[str] = mapped_column(GUID(), primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    business_name: Mapped[str] = mapped_column(String(255), nullable=False)
    contact_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    owner_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    phone: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    email: Mapped[str] = mapped_column(String(255), nullable=False, default="", index=True)
    address: Mapped[str] = mapped_column(Text, nullable=False, default="")
    currency_code: Mapped[str] = mapped_column(String(16), nullable=False, default="USD")
    currency_symbol: Mapped[str] = mapped_column(String(8), nullable=False, default="$")
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="UTC")
    website_url: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    facebook_url: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    instagram_url: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    whatsapp_number: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active", index=True)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")


class ClientSettingsModel(TenantMixin, TimestampMixin, Base):
    __tablename__ = "client_settings"

    client_settings_id: Mapped[str] = mapped_column(GUID(), primary_key=True)
    low_stock_threshold: Mapped[Decimal] = mapped_column(Quantity, nullable=False, default=Decimal("5"))
    allow_backorder: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    default_location_name: Mapped[str] = mapped_column(String(128), nullable=False, default="Main Warehouse")
    require_discount_approval: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    order_prefix: Mapped[str] = mapped_column(String(16), nullable=False, default="SO")
    purchase_prefix: Mapped[str] = mapped_column(String(16), nullable=False, default="PO")
    return_prefix: Mapped[str] = mapped_column(String(16), nullable=False, default="RT")


class RoleModel(Base):
    __tablename__ = "roles"

    role_code: Mapped[str] = mapped_column(String(64), primary_key=True)
    role_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")


class UserModel(TenantMixin, TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("email", name="uq_users_email"),
        UniqueConstraint("user_code", name="uq_users_user_code"),
    )

    user_id: Mapped[str] = mapped_column(GUID(), primary_key=True)
    user_code: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    password: Mapped[str] = mapped_column(Text, nullable=False, default="")
    password_hash: Mapped[str] = mapped_column(Text, nullable=False, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_login_at: Mapped[datetime | None] = mapped_column(Timestamp)
    invited_at: Mapped[datetime | None] = mapped_column(Timestamp)


class UserRoleModel(Base):
    __tablename__ = "user_roles"

    user_id: Mapped[str] = mapped_column(
        GUID(),
        ForeignKey("users.user_id", ondelete="CASCADE"),
        primary_key=True,
    )
    role_code: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("roles.role_code", ondelete="CASCADE"),
        primary_key=True,
    )


class UserPageAccessOverrideModel(TimestampMixin, Base):
    __tablename__ = "user_page_access_overrides"
    __table_args__ = (
        UniqueConstraint("user_id", "page_code", name="uq_user_page_access_overrides_user_page"),
    )

    override_id: Mapped[str] = mapped_column(GUID(), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        GUID(),
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    page_code: Mapped[str] = mapped_column(String(64), nullable=False)
    is_allowed: Mapped[bool] = mapped_column(Boolean, nullable=False)


class AuditLogModel(Base):
    __tablename__ = "audit_log"
    __table_args__ = (
        Index("ix_audit_log_client_entity", "client_id", "entity_type", "entity_id"),
    )

    audit_log_id: Mapped[str] = mapped_column(GUID(), primary_key=True)
    client_id: Mapped[str | None] = mapped_column(GUID(), ForeignKey("clients.client_id", ondelete="CASCADE"))
    actor_user_id: Mapped[str | None] = mapped_column(GUID(), ForeignKey("users.user_id", ondelete="SET NULL"))
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(64), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    request_id: Mapped[str | None] = mapped_column(String(64), index=True)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(Timestamp, server_default=func.now(), nullable=False)


class CategoryModel(TenantMixin, TimestampMixin, Base):
    __tablename__ = "categories"
    __table_args__ = (
        UniqueConstraint("client_id", "slug", name="uq_categories_client_slug"),
    )

    category_id: Mapped[str] = mapped_column(GUID(), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active", index=True)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")


class SupplierModel(TenantMixin, TimestampMixin, Base):
    __tablename__ = "suppliers"
    __table_args__ = (
        UniqueConstraint("client_id", "code", name="uq_suppliers_client_code"),
    )

    supplier_id: Mapped[str] = mapped_column(GUID(), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    contact_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    email: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    phone: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    address: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active", index=True)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")


class LocationModel(TenantMixin, TimestampMixin, Base):
    __tablename__ = "locations"
    __table_args__ = (
        UniqueConstraint("client_id", "code", name="uq_locations_client_code"),
    )

    location_id: Mapped[str] = mapped_column(GUID(), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active", index=True)


class ProductModel(TenantMixin, TimestampMixin, Base):
    __tablename__ = "products"
    __table_args__ = (
        UniqueConstraint("client_id", "slug", name="uq_products_client_slug"),
        Index("ix_products_client_name", "client_id", "name"),
    )

    product_id: Mapped[str] = mapped_column(GUID(), primary_key=True)
    category_id: Mapped[str | None] = mapped_column(GUID(), ForeignKey("categories.category_id", ondelete="SET NULL"))
    supplier_id: Mapped[str | None] = mapped_column(GUID(), ForeignKey("suppliers.supplier_id", ondelete="SET NULL"))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(128), nullable=False)
    sku_root: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    brand: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    image_url: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft", index=True)
    default_price_amount: Mapped[Decimal | None] = mapped_column(Amount)
    min_price_amount: Mapped[Decimal | None] = mapped_column(Amount)
    max_discount_percent: Mapped[Decimal | None] = mapped_column(Percent)


class ProductVariantModel(TenantMixin, TimestampMixin, Base):
    __tablename__ = "product_variants"
    __table_args__ = (
        UniqueConstraint("client_id", "sku", name="uq_product_variants_client_sku"),
        Index("ix_product_variants_client_title", "client_id", "title"),
        Index("ix_product_variants_client_barcode", "client_id", "barcode"),
    )

    variant_id: Mapped[str] = mapped_column(GUID(), primary_key=True)
    product_id: Mapped[str] = mapped_column(GUID(), ForeignKey("products.product_id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    sku: Mapped[str] = mapped_column(String(128), nullable=False)
    barcode: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    option_values_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active", index=True)
    cost_amount: Mapped[Decimal | None] = mapped_column(Amount)
    price_amount: Mapped[Decimal | None] = mapped_column(Amount)
    min_price_amount: Mapped[Decimal | None] = mapped_column(Amount)
    reorder_level: Mapped[Decimal] = mapped_column(Quantity, nullable=False, default=Decimal("0"))


class PurchaseModel(TenantMixin, TimestampMixin, Base):
    __tablename__ = "purchases"
    __table_args__ = (
        UniqueConstraint("client_id", "purchase_number", name="uq_purchases_client_number"),
    )

    purchase_id: Mapped[str] = mapped_column(GUID(), primary_key=True)
    supplier_id: Mapped[str | None] = mapped_column(GUID(), ForeignKey("suppliers.supplier_id", ondelete="SET NULL"))
    location_id: Mapped[str] = mapped_column(GUID(), ForeignKey("locations.location_id"), nullable=False)
    purchase_number: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft", index=True)
    ordered_at: Mapped[datetime | None] = mapped_column(Timestamp)
    received_at: Mapped[datetime | None] = mapped_column(Timestamp)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_by_user_id: Mapped[str | None] = mapped_column(GUID(), ForeignKey("users.user_id", ondelete="SET NULL"))
    subtotal_amount: Mapped[Decimal] = mapped_column(Amount, nullable=False, default=Decimal("0"))
    total_amount: Mapped[Decimal] = mapped_column(Amount, nullable=False, default=Decimal("0"))


class PurchaseItemModel(TenantMixin, Base):
    __tablename__ = "purchase_items"

    purchase_item_id: Mapped[str] = mapped_column(GUID(), primary_key=True)
    purchase_id: Mapped[str] = mapped_column(GUID(), ForeignKey("purchases.purchase_id", ondelete="CASCADE"), nullable=False, index=True)
    variant_id: Mapped[str] = mapped_column(GUID(), ForeignKey("product_variants.variant_id"), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Quantity, nullable=False, default=Decimal("0"))
    received_quantity: Mapped[Decimal] = mapped_column(Quantity, nullable=False, default=Decimal("0"))
    unit_cost_amount: Mapped[Decimal] = mapped_column(Amount, nullable=False, default=Decimal("0"))
    line_total_amount: Mapped[Decimal] = mapped_column(Amount, nullable=False, default=Decimal("0"))
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(Timestamp, server_default=func.now(), nullable=False)


class InventoryLedgerModel(TenantMixin, Base):
    __tablename__ = "inventory_ledger"
    __table_args__ = (
        Index("ix_inventory_ledger_variant_location", "client_id", "variant_id", "location_id"),
        Index("ix_inventory_ledger_reference", "reference_type", "reference_id"),
    )

    entry_id: Mapped[str] = mapped_column(GUID(), primary_key=True)
    variant_id: Mapped[str] = mapped_column(GUID(), ForeignKey("product_variants.variant_id"), nullable=False)
    location_id: Mapped[str] = mapped_column(GUID(), ForeignKey("locations.location_id"), nullable=False)
    movement_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    reference_type: Mapped[str] = mapped_column(String(64), nullable=False)
    reference_id: Mapped[str] = mapped_column(String(64), nullable=False)
    reference_line_id: Mapped[str | None] = mapped_column(String(64))
    quantity_delta: Mapped[Decimal] = mapped_column(Quantity, nullable=False)
    unit_cost_amount: Mapped[Decimal | None] = mapped_column(Amount)
    unit_price_amount: Mapped[Decimal | None] = mapped_column(Amount)
    reason: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    created_by_user_id: Mapped[str | None] = mapped_column(GUID(), ForeignKey("users.user_id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(Timestamp, server_default=func.now(), nullable=False)


class CustomerModel(TenantMixin, TimestampMixin, Base):
    __tablename__ = "customers"
    __table_args__ = (
        UniqueConstraint("client_id", "code", name="uq_customers_client_code"),
        Index("ix_customers_client_phone_normalized", "client_id", "phone_normalized"),
        Index("ix_customers_client_email_normalized", "client_id", "email_normalized"),
    )

    customer_id: Mapped[str] = mapped_column(GUID(), primary_key=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    email_normalized: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    phone: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    phone_normalized: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    whatsapp_number: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    address: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active", index=True)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")


class SalesOrderModel(TenantMixin, TimestampMixin, Base):
    __tablename__ = "sales_orders"
    __table_args__ = (
        UniqueConstraint("client_id", "order_number", name="uq_sales_orders_client_number"),
    )

    sales_order_id: Mapped[str] = mapped_column(GUID(), primary_key=True)
    customer_id: Mapped[str | None] = mapped_column(GUID(), ForeignKey("customers.customer_id", ondelete="SET NULL"))
    location_id: Mapped[str] = mapped_column(GUID(), ForeignKey("locations.location_id"), nullable=False)
    order_number: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft", index=True)
    payment_status: Mapped[str] = mapped_column(String(32), nullable=False, default="unpaid", index=True)
    shipment_status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", index=True)
    ordered_at: Mapped[datetime | None] = mapped_column(Timestamp)
    confirmed_at: Mapped[datetime | None] = mapped_column(Timestamp)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_by_user_id: Mapped[str | None] = mapped_column(GUID(), ForeignKey("users.user_id", ondelete="SET NULL"))
    subtotal_amount: Mapped[Decimal] = mapped_column(Amount, nullable=False, default=Decimal("0"))
    discount_amount: Mapped[Decimal] = mapped_column(Amount, nullable=False, default=Decimal("0"))
    total_amount: Mapped[Decimal] = mapped_column(Amount, nullable=False, default=Decimal("0"))
    paid_amount: Mapped[Decimal] = mapped_column(Amount, nullable=False, default=Decimal("0"))


class SalesOrderItemModel(TenantMixin, Base):
    __tablename__ = "sales_order_items"

    sales_order_item_id: Mapped[str] = mapped_column(GUID(), primary_key=True)
    sales_order_id: Mapped[str] = mapped_column(GUID(), ForeignKey("sales_orders.sales_order_id", ondelete="CASCADE"), nullable=False, index=True)
    variant_id: Mapped[str] = mapped_column(GUID(), ForeignKey("product_variants.variant_id"), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Quantity, nullable=False, default=Decimal("0"))
    quantity_fulfilled: Mapped[Decimal] = mapped_column(Quantity, nullable=False, default=Decimal("0"))
    quantity_cancelled: Mapped[Decimal] = mapped_column(Quantity, nullable=False, default=Decimal("0"))
    unit_price_amount: Mapped[Decimal] = mapped_column(Amount, nullable=False, default=Decimal("0"))
    discount_amount: Mapped[Decimal] = mapped_column(Amount, nullable=False, default=Decimal("0"))
    line_total_amount: Mapped[Decimal] = mapped_column(Amount, nullable=False, default=Decimal("0"))
    created_at: Mapped[datetime] = mapped_column(Timestamp, server_default=func.now(), nullable=False)


class PaymentModel(TenantMixin, TimestampMixin, Base):
    __tablename__ = "payments"

    payment_id: Mapped[str] = mapped_column(GUID(), primary_key=True)
    sales_order_id: Mapped[str | None] = mapped_column(GUID(), ForeignKey("sales_orders.sales_order_id", ondelete="SET NULL"))
    sales_return_id: Mapped[str | None] = mapped_column(GUID(), ForeignKey("sales_returns.sales_return_id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", index=True)
    method: Mapped[str] = mapped_column(String(64), nullable=False, default="manual")
    amount: Mapped[Decimal] = mapped_column(Amount, nullable=False, default=Decimal("0"))
    paid_at: Mapped[datetime | None] = mapped_column(Timestamp)
    reference: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_by_user_id: Mapped[str | None] = mapped_column(GUID(), ForeignKey("users.user_id", ondelete="SET NULL"))


class ShipmentModel(TenantMixin, TimestampMixin, Base):
    __tablename__ = "shipments"

    shipment_id: Mapped[str] = mapped_column(GUID(), primary_key=True)
    sales_order_id: Mapped[str] = mapped_column(GUID(), ForeignKey("sales_orders.sales_order_id", ondelete="CASCADE"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", index=True)
    tracking_number: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    carrier: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    shipped_at: Mapped[datetime | None] = mapped_column(Timestamp)
    delivered_at: Mapped[datetime | None] = mapped_column(Timestamp)
    failed_at: Mapped[datetime | None] = mapped_column(Timestamp)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")


class SalesReturnModel(TenantMixin, TimestampMixin, Base):
    __tablename__ = "sales_returns"
    __table_args__ = (
        UniqueConstraint("client_id", "return_number", name="uq_sales_returns_client_number"),
    )

    sales_return_id: Mapped[str] = mapped_column(GUID(), primary_key=True)
    sales_order_id: Mapped[str | None] = mapped_column(GUID(), ForeignKey("sales_orders.sales_order_id", ondelete="SET NULL"))
    customer_id: Mapped[str | None] = mapped_column(GUID(), ForeignKey("customers.customer_id", ondelete="SET NULL"))
    return_number: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", index=True)
    refund_status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", index=True)
    requested_at: Mapped[datetime | None] = mapped_column(Timestamp)
    approved_at: Mapped[datetime | None] = mapped_column(Timestamp)
    received_at: Mapped[datetime | None] = mapped_column(Timestamp)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_by_user_id: Mapped[str | None] = mapped_column(GUID(), ForeignKey("users.user_id", ondelete="SET NULL"))
    subtotal_amount: Mapped[Decimal] = mapped_column(Amount, nullable=False, default=Decimal("0"))
    refund_amount: Mapped[Decimal] = mapped_column(Amount, nullable=False, default=Decimal("0"))


class SalesReturnItemModel(TenantMixin, Base):
    __tablename__ = "sales_return_items"

    sales_return_item_id: Mapped[str] = mapped_column(GUID(), primary_key=True)
    sales_return_id: Mapped[str] = mapped_column(GUID(), ForeignKey("sales_returns.sales_return_id", ondelete="CASCADE"), nullable=False, index=True)
    sales_order_item_id: Mapped[str | None] = mapped_column(GUID(), ForeignKey("sales_order_items.sales_order_item_id", ondelete="SET NULL"))
    variant_id: Mapped[str] = mapped_column(GUID(), ForeignKey("product_variants.variant_id"), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Quantity, nullable=False, default=Decimal("0"))
    restock_quantity: Mapped[Decimal] = mapped_column(Quantity, nullable=False, default=Decimal("0"))
    unit_refund_amount: Mapped[Decimal] = mapped_column(Amount, nullable=False, default=Decimal("0"))
    disposition: Mapped[str] = mapped_column(String(64), nullable=False, default="restock")
    created_at: Mapped[datetime] = mapped_column(Timestamp, server_default=func.now(), nullable=False)


class RefundModel(TenantMixin, TimestampMixin, Base):
    __tablename__ = "refunds"

    refund_id: Mapped[str] = mapped_column(GUID(), primary_key=True)
    sales_return_id: Mapped[str] = mapped_column(GUID(), ForeignKey("sales_returns.sales_return_id", ondelete="CASCADE"), nullable=False, index=True)
    payment_id: Mapped[str | None] = mapped_column(GUID(), ForeignKey("payments.payment_id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", index=True)
    amount: Mapped[Decimal] = mapped_column(Amount, nullable=False, default=Decimal("0"))
    refunded_at: Mapped[datetime | None] = mapped_column(Timestamp)
    reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_by_user_id: Mapped[str | None] = mapped_column(GUID(), ForeignKey("users.user_id", ondelete="SET NULL"))


class ExpenseModel(TenantMixin, TimestampMixin, Base):
    __tablename__ = "expenses"
    __table_args__ = (
        UniqueConstraint("client_id", "expense_number", name="uq_expenses_client_number"),
    )

    expense_id: Mapped[str] = mapped_column(GUID(), primary_key=True)
    expense_number: Mapped[str] = mapped_column(String(64), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False, default="general")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    vendor_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    amount: Mapped[Decimal] = mapped_column(Amount, nullable=False, default=Decimal("0"))
    incurred_at: Mapped[datetime] = mapped_column(Timestamp, nullable=False, server_default=func.now())
    payment_status: Mapped[str] = mapped_column(String(32), nullable=False, default="unpaid", index=True)
    created_by_user_id: Mapped[str | None] = mapped_column(GUID(), ForeignKey("users.user_id", ondelete="SET NULL"))
