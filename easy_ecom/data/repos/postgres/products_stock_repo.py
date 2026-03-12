from __future__ import annotations

from easy_ecom.data.repos.postgres.base import PostgresRepo
from easy_ecom.data.store.postgres_models import (
    CategoryModel,
    ClientModel,
    InventoryTxnModel,
    ProductModel,
    ProductVariantModel,
    SupplierModel,
    UserModel,
)


class ClientsPostgresRepo(PostgresRepo):
    model = ClientModel
    columns = [
        "client_id",
        "business_name",
        "owner_name",
        "phone",
        "email",
        "address",
        "currency_code",
        "currency_symbol",
        "website_url",
        "facebook_url",
        "instagram_url",
        "whatsapp_number",
        "created_at",
        "status",
        "notes",
    ]


class UsersPostgresRepo(PostgresRepo):
    model = UserModel
    columns = ["user_id", "client_id", "name", "email", "password", "is_active", "created_at"]


class CategoriesPostgresRepo(PostgresRepo):
    model = CategoryModel
    columns = ["category_id", "client_id", "name", "description", "created_at", "is_active"]


class SuppliersPostgresRepo(PostgresRepo):
    model = SupplierModel
    columns = [
        "supplier_id",
        "client_id",
        "name",
        "contact_name",
        "phone",
        "email",
        "created_at",
        "is_active",
    ]


class ProductsPostgresRepo(PostgresRepo):
    model = ProductModel
    columns = [
        "product_id",
        "client_id",
        "supplier",
        "product_name",
        "category",
        "prd_description",
        "prd_features_json",
        "created_at",
        "is_active",
        "is_parent",
        "sizes_csv",
        "colors_csv",
        "others_csv",
        "parent_product_id",
    ]


class ProductVariantsPostgresRepo(PostgresRepo):
    model = ProductVariantModel
    columns = [
        "variant_id",
        "client_id",
        "parent_product_id",
        "variant_name",
        "size",
        "color",
        "other",
        "sku_code",
        "default_selling_price",
        "max_discount_pct",
        "is_active",
        "created_at",
    ]


class InventoryTxnPostgresRepo(PostgresRepo):
    model = InventoryTxnModel
    columns = [
        "txn_id",
        "client_id",
        "timestamp",
        "user_id",
        "txn_type",
        "product_id",
        "variant_id",
        "product_name",
        "qty",
        "unit_cost",
        "total_cost",
        "supplier_snapshot",
        "note",
        "source_type",
        "source_id",
        "lot_id",
    ]
