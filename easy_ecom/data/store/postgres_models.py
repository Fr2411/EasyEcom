from __future__ import annotations

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from easy_ecom.data.store.postgres_db import Base


class ClientModel(Base):
    __tablename__ = "clients"

    client_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    business_name: Mapped[str] = mapped_column(String(255), default="")
    owner_name: Mapped[str] = mapped_column(String(255), default="")
    phone: Mapped[str] = mapped_column(String(64), default="")
    email: Mapped[str] = mapped_column(String(255), default="")
    address: Mapped[str] = mapped_column(Text, default="")
    currency_code: Mapped[str] = mapped_column(String(16), default="")
    currency_symbol: Mapped[str] = mapped_column(String(8), default="")
    website_url: Mapped[str] = mapped_column(String(255), default="")
    facebook_url: Mapped[str] = mapped_column(String(255), default="")
    instagram_url: Mapped[str] = mapped_column(String(255), default="")
    whatsapp_number: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[str] = mapped_column(String(64), default="")
    status: Mapped[str] = mapped_column(String(32), default="")
    notes: Mapped[str] = mapped_column(Text, default="")


class UserModel(Base):
    __tablename__ = "users"

    user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    client_id: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(255), default="")
    email: Mapped[str] = mapped_column(String(255), default="")
    password: Mapped[str] = mapped_column(Text, default="")
    password_hash: Mapped[str] = mapped_column(Text, default="")
    is_active: Mapped[str] = mapped_column(String(8), default="true")
    created_at: Mapped[str] = mapped_column(String(64), default="")


class UserRoleModel(Base):
    __tablename__ = "user_roles"

    user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    role_code: Mapped[str] = mapped_column(String(64), primary_key=True)


class CategoryModel(Base):
    __tablename__ = "categories"

    category_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    client_id: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[str] = mapped_column(String(64), default="")
    is_active: Mapped[str] = mapped_column(String(8), default="true")


class SupplierModel(Base):
    __tablename__ = "suppliers"

    supplier_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    client_id: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    contact_name: Mapped[str] = mapped_column(String(255), default="")
    phone: Mapped[str] = mapped_column(String(64), default="")
    email: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[str] = mapped_column(String(64), default="")
    is_active: Mapped[str] = mapped_column(String(8), default="true")


class CustomerModel(Base):
    __tablename__ = "customers"

    customer_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    client_id: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[str] = mapped_column(String(64), default="")
    updated_at: Mapped[str] = mapped_column(String(64), default="")
    full_name: Mapped[str] = mapped_column(String(255), index=True)
    phone: Mapped[str] = mapped_column(String(64), default="")
    email: Mapped[str] = mapped_column(String(255), default="")
    whatsapp: Mapped[str] = mapped_column(String(64), default="")
    address_line1: Mapped[str] = mapped_column(String(255), default="")
    address_line2: Mapped[str] = mapped_column(String(255), default="")
    area: Mapped[str] = mapped_column(String(255), default="")
    city: Mapped[str] = mapped_column(String(128), default="")
    state: Mapped[str] = mapped_column(String(128), default="")
    postal_code: Mapped[str] = mapped_column(String(32), default="")
    country: Mapped[str] = mapped_column(String(128), default="")
    preferred_contact_channel: Mapped[str] = mapped_column(String(32), default="phone")
    marketing_opt_in: Mapped[str] = mapped_column(String(8), default="false")
    tags: Mapped[str] = mapped_column(Text, default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    is_active: Mapped[str] = mapped_column(String(8), default="true")


class ProductModel(Base):
    __tablename__ = "products"

    product_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    client_id: Mapped[str] = mapped_column(String(64), index=True)
    supplier: Mapped[str] = mapped_column(String(255), default="")
    product_name: Mapped[str] = mapped_column(String(255), index=True)
    category: Mapped[str] = mapped_column(String(255), default="")
    prd_description: Mapped[str] = mapped_column(Text, default="")
    prd_features_json: Mapped[str] = mapped_column(Text, default="")
    default_selling_price: Mapped[str] = mapped_column(String(64), default="0")
    max_discount_pct: Mapped[str] = mapped_column(String(64), default="0")
    created_at: Mapped[str] = mapped_column(String(64), default="")
    is_active: Mapped[str] = mapped_column(String(8), default="true")
    is_parent: Mapped[str] = mapped_column(String(8), default="true")
    sizes_csv: Mapped[str] = mapped_column(Text, default="")
    colors_csv: Mapped[str] = mapped_column(Text, default="")
    others_csv: Mapped[str] = mapped_column(Text, default="")
    parent_product_id: Mapped[str] = mapped_column(String(64), default="")


class ProductVariantModel(Base):
    __tablename__ = "product_variants"

    variant_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    client_id: Mapped[str] = mapped_column(String(64), index=True)
    parent_product_id: Mapped[str] = mapped_column(String(64), index=True)
    variant_name: Mapped[str] = mapped_column(String(255), default="")
    size: Mapped[str] = mapped_column(String(64), default="")
    color: Mapped[str] = mapped_column(String(64), default="")
    other: Mapped[str] = mapped_column(String(64), default="")
    sku_code: Mapped[str] = mapped_column(String(128), default="")
    default_selling_price: Mapped[str] = mapped_column(String(64), default="0")
    max_discount_pct: Mapped[str] = mapped_column(String(64), default="0")
    is_active: Mapped[str] = mapped_column(String(8), default="true")
    created_at: Mapped[str] = mapped_column(String(64), default="")


class InventoryTxnModel(Base):
    __tablename__ = "inventory_txn"

    txn_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    client_id: Mapped[str] = mapped_column(String(64), index=True)
    timestamp: Mapped[str] = mapped_column(String(64), default="")
    user_id: Mapped[str] = mapped_column(String(64), default="")
    txn_type: Mapped[str] = mapped_column(String(32), default="")
    product_id: Mapped[str] = mapped_column(String(64), index=True)
    product_name: Mapped[str] = mapped_column(String(255), default="")
    qty: Mapped[str] = mapped_column(String(64), default="0")
    unit_cost: Mapped[str] = mapped_column(String(64), default="0")
    total_cost: Mapped[str] = mapped_column(String(64), default="0")
    supplier_snapshot: Mapped[str] = mapped_column(String(255), default="")
    note: Mapped[str] = mapped_column(Text, default="")
    source_type: Mapped[str] = mapped_column(String(64), default="")
    source_id: Mapped[str] = mapped_column(String(64), default="")
    lot_id: Mapped[str] = mapped_column(String(64), default="")


class SalesOrderModel(Base):
    __tablename__ = "sales_orders"

    order_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    client_id: Mapped[str] = mapped_column(String(64), index=True)
    sale_no: Mapped[str] = mapped_column(String(64), index=True, default="")
    timestamp: Mapped[str] = mapped_column(String(64), default="")
    customer_id: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(32), default="confirmed")
    subtotal: Mapped[str] = mapped_column(String(64), default="0")
    discount: Mapped[str] = mapped_column(String(64), default="0")
    tax: Mapped[str] = mapped_column(String(64), default="0")
    grand_total: Mapped[str] = mapped_column(String(64), default="0")
    amount_paid: Mapped[str] = mapped_column(String(64), default="0")
    outstanding_balance: Mapped[str] = mapped_column(String(64), default="0")
    payment_status: Mapped[str] = mapped_column(String(32), default="unpaid")
    note: Mapped[str] = mapped_column(Text, default="")
    created_by_user_id: Mapped[str] = mapped_column(String(64), default="")


class SalesOrderItemModel(Base):
    __tablename__ = "sales_order_items"

    order_item_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    order_id: Mapped[str] = mapped_column(String(64), index=True)
    client_id: Mapped[str] = mapped_column(String(64), index=True)
    product_id: Mapped[str] = mapped_column(String(64), index=True)
    product_name_snapshot: Mapped[str] = mapped_column(String(255), default="")
    qty: Mapped[str] = mapped_column(String(64), default="0")
    unit_selling_price: Mapped[str] = mapped_column(String(64), default="0")
    total_selling_price: Mapped[str] = mapped_column(String(64), default="0")


class FinanceExpenseModel(Base):
    __tablename__ = "finance_expenses"

    expense_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    client_id: Mapped[str] = mapped_column(String(64), index=True)
    expense_date: Mapped[str] = mapped_column(String(32), index=True, default="")
    category: Mapped[str] = mapped_column(String(120), index=True, default="")
    amount: Mapped[str] = mapped_column(String(64), default="0")
    payment_status: Mapped[str] = mapped_column(String(32), default="paid")
    note: Mapped[str] = mapped_column(Text, default="")
    created_by_user_id: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[str] = mapped_column(String(64), default="")
    updated_at: Mapped[str] = mapped_column(String(64), default="")


class ImportRunModel(Base):
    __tablename__ = "import_runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    entity_name: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    source_file: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(20), index=True, nullable=False, default="running")
    total_rows: Mapped[str] = mapped_column(String(32), default="0")
    inserted_rows: Mapped[str] = mapped_column(String(32), default="0")
    updated_rows: Mapped[str] = mapped_column(String(32), default="0")
    skipped_rows: Mapped[str] = mapped_column(String(32), default="0")
    failed_rows: Mapped[str] = mapped_column(String(32), default="0")
    notes: Mapped[str] = mapped_column(Text, default="")
    started_at: Mapped[str] = mapped_column(String(64), default="")
    finished_at: Mapped[str] = mapped_column(String(64), default="")


class ImportErrorModel(Base):
    __tablename__ = "import_errors"

    error_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    import_run_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    row_number: Mapped[str] = mapped_column(String(32), default="")
    raw_data: Mapped[str] = mapped_column(Text, default="")
    error_message: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(String(64), default="")
