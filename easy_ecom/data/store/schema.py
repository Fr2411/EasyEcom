from __future__ import annotations

TABLE_SCHEMAS: dict[str, list[str]] = {
    "clients.csv": ["client_id", "business_name", "owner_name", "phone", "email", "address", "currency_code", "currency_symbol", "website_url", "facebook_url", "instagram_url", "whatsapp_number", "created_at", "status", "notes"],
    "users.csv": ["user_id", "client_id", "name", "email", "password", "is_active", "created_at"],
    "roles.csv": ["role_code", "role_name", "description"],
    "user_roles.csv": ["user_id", "role_code"],
    "products.csv": ["product_id", "client_id", "supplier", "product_name", "category", "prd_description", "prd_features_json", "default_selling_price", "max_discount_pct", "created_at", "is_active"],
    "customers.csv": ["customer_id", "client_id", "created_at", "full_name", "phone", "email", "whatsapp", "address_line1", "address_line2", "area", "city", "state", "postal_code", "country", "preferred_contact_channel", "marketing_opt_in", "tags", "notes", "is_active"],
    "inventory_txn.csv": ["txn_id", "client_id", "timestamp", "user_id", "txn_type", "product_id", "qty", "unit_cost", "total_cost", "supplier_snapshot", "note", "source_type", "source_id", "lot_id"],
    "sales_orders.csv": ["order_id", "client_id", "timestamp", "customer_id", "status", "subtotal", "discount", "tax", "grand_total", "note"],
    "sales_order_items.csv": ["order_item_id", "order_id", "product_id", "prd_description_snapshot", "qty", "unit_selling_price", "total_selling_price"],
    "invoices.csv": ["invoice_id", "client_id", "invoice_no", "order_id", "customer_id", "timestamp", "amount_due", "status"],
    "shipments.csv": ["shipment_id", "client_id", "shipment_no", "order_id", "customer_id", "timestamp", "status", "ship_to_name_snapshot", "ship_to_phone_snapshot", "ship_to_address_snapshot", "courier", "tracking_no"],
    "payments.csv": ["payment_id", "client_id", "timestamp", "invoice_id", "amount_paid", "method", "note"],
    "ledger.csv": ["entry_id", "client_id", "timestamp", "user_id", "entry_type", "category", "amount", "source_type", "source_id", "note"],
    "sequences.csv": ["client_id", "sequence_key", "year", "last_number"],
    "audit_log.csv": ["event_id", "timestamp", "user_id", "client_id", "action", "entity_type", "entity_id", "details_json"],
    "returns.csv": ["return_id", "client_id", "invoice_id", "order_id", "customer_id", "status", "requested_by_user_id", "approved_by_user_id", "requested_at", "approved_at", "reason", "note", "restock"],
    "return_items.csv": ["return_item_id", "return_id", "product_id", "qty", "unit_selling_price", "refund_amount", "note"],
    "refunds.csv": ["refund_id", "client_id", "return_id", "invoice_id", "order_id", "customer_id", "amount", "status", "requested_by_user_id", "approved_by_user_id", "created_at", "processed_at", "reason", "note"],
}

ROLES_SEED = [
    {"role_code": "SUPER_ADMIN", "role_name": "Super Admin", "description": "Global system administrator"},
    {"role_code": "CLIENT_OWNER", "role_name": "Client Owner", "description": "Full client access"},
    {"role_code": "CLIENT_MANAGER", "role_name": "Client Manager", "description": "Operations management"},
    {"role_code": "CLIENT_EMPLOYEE", "role_name": "Client Employee", "description": "Operational access"},
    {"role_code": "FINANCE_ONLY", "role_name": "Finance Only", "description": "Finance team access"},
]
