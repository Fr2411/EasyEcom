from __future__ import annotations

from sqlalchemy import String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


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
    is_active: Mapped[str] = mapped_column(String(8), default="true")
    created_at: Mapped[str] = mapped_column(String(64), default="")


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
