BEGIN;

CREATE TABLE clients (
    client_id UUID PRIMARY KEY,
    slug VARCHAR(64) NOT NULL UNIQUE,
    business_name VARCHAR(255) NOT NULL,
    owner_name VARCHAR(255) NOT NULL DEFAULT '',
    phone VARCHAR(64) NOT NULL DEFAULT '',
    email VARCHAR(255) NOT NULL DEFAULT '',
    address TEXT NOT NULL DEFAULT '',
    currency_code VARCHAR(16) NOT NULL DEFAULT 'USD',
    currency_symbol VARCHAR(8) NOT NULL DEFAULT '$',
    timezone VARCHAR(64) NOT NULL DEFAULT 'UTC',
    website_url VARCHAR(255) NOT NULL DEFAULT '',
    facebook_url VARCHAR(255) NOT NULL DEFAULT '',
    instagram_url VARCHAR(255) NOT NULL DEFAULT '',
    whatsapp_number VARCHAR(64) NOT NULL DEFAULT '',
    status VARCHAR(32) NOT NULL DEFAULT 'active',
    notes TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_clients_email ON clients (email);
CREATE INDEX ix_clients_status ON clients (status);

CREATE TABLE client_settings (
    client_settings_id UUID PRIMARY KEY,
    client_id UUID NOT NULL REFERENCES clients (client_id) ON DELETE CASCADE,
    low_stock_threshold NUMERIC(14, 3) NOT NULL DEFAULT 5,
    allow_backorder BOOLEAN NOT NULL DEFAULT FALSE,
    default_location_name VARCHAR(128) NOT NULL DEFAULT 'Main Warehouse',
    require_discount_approval BOOLEAN NOT NULL DEFAULT FALSE,
    order_prefix VARCHAR(16) NOT NULL DEFAULT 'SO',
    purchase_prefix VARCHAR(16) NOT NULL DEFAULT 'PO',
    return_prefix VARCHAR(16) NOT NULL DEFAULT 'RT',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX uq_client_settings_client_id ON client_settings (client_id);

CREATE TABLE roles (
    role_code VARCHAR(64) PRIMARY KEY,
    role_name VARCHAR(255) NOT NULL,
    description TEXT NOT NULL DEFAULT ''
);

CREATE TABLE users (
    user_id UUID PRIMARY KEY,
    client_id UUID NOT NULL REFERENCES clients (client_id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    password TEXT NOT NULL DEFAULT '',
    password_hash TEXT NOT NULL DEFAULT '',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    last_login_at TIMESTAMPTZ,
    invited_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_users_client_id ON users (client_id);
CREATE INDEX ix_users_email ON users (email);

CREATE TABLE user_roles (
    user_id UUID NOT NULL REFERENCES users (user_id) ON DELETE CASCADE,
    role_code VARCHAR(64) NOT NULL REFERENCES roles (role_code) ON DELETE CASCADE,
    PRIMARY KEY (user_id, role_code)
);

CREATE TABLE user_invitations (
    invitation_id UUID PRIMARY KEY,
    client_id UUID NOT NULL REFERENCES clients (client_id) ON DELETE CASCADE,
    email VARCHAR(255) NOT NULL,
    role_code VARCHAR(64) NOT NULL REFERENCES roles (role_code),
    invited_by_user_id UUID NOT NULL REFERENCES users (user_id),
    token_hash VARCHAR(128) NOT NULL UNIQUE,
    expires_at TIMESTAMPTZ NOT NULL,
    accepted_at TIMESTAMPTZ,
    status VARCHAR(32) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_user_invitations_client_id ON user_invitations (client_id);
CREATE INDEX ix_user_invitations_email ON user_invitations (email);
CREATE INDEX ix_user_invitations_status ON user_invitations (status);

CREATE TABLE password_reset_tokens (
    reset_token_id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users (user_id) ON DELETE CASCADE,
    token_hash VARCHAR(128) NOT NULL UNIQUE,
    expires_at TIMESTAMPTZ NOT NULL,
    consumed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_password_reset_tokens_user_id ON password_reset_tokens (user_id);

CREATE TABLE audit_log (
    audit_log_id UUID PRIMARY KEY,
    client_id UUID REFERENCES clients (client_id) ON DELETE CASCADE,
    actor_user_id UUID REFERENCES users (user_id) ON DELETE SET NULL,
    entity_type VARCHAR(64) NOT NULL,
    entity_id VARCHAR(64) NOT NULL,
    action VARCHAR(64) NOT NULL,
    request_id VARCHAR(64),
    metadata_json JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_audit_log_client_entity ON audit_log (client_id, entity_type, entity_id);
CREATE INDEX ix_audit_log_request_id ON audit_log (request_id);

CREATE TABLE categories (
    category_id UUID PRIMARY KEY,
    client_id UUID NOT NULL REFERENCES clients (client_id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(128) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'active',
    notes TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (client_id, slug)
);

CREATE INDEX ix_categories_client_id ON categories (client_id);
CREATE INDEX ix_categories_status ON categories (status);

CREATE TABLE suppliers (
    supplier_id UUID PRIMARY KEY,
    client_id UUID NOT NULL REFERENCES clients (client_id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    code VARCHAR(64) NOT NULL,
    contact_name VARCHAR(255) NOT NULL DEFAULT '',
    email VARCHAR(255) NOT NULL DEFAULT '',
    phone VARCHAR(64) NOT NULL DEFAULT '',
    address TEXT NOT NULL DEFAULT '',
    status VARCHAR(32) NOT NULL DEFAULT 'active',
    notes TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (client_id, code)
);

CREATE INDEX ix_suppliers_client_id ON suppliers (client_id);
CREATE INDEX ix_suppliers_status ON suppliers (status);

CREATE TABLE locations (
    location_id UUID PRIMARY KEY,
    client_id UUID NOT NULL REFERENCES clients (client_id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    code VARCHAR(64) NOT NULL,
    is_default BOOLEAN NOT NULL DEFAULT FALSE,
    status VARCHAR(32) NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (client_id, code)
);

CREATE INDEX ix_locations_client_id ON locations (client_id);
CREATE INDEX ix_locations_status ON locations (status);

CREATE TABLE products (
    product_id UUID PRIMARY KEY,
    client_id UUID NOT NULL REFERENCES clients (client_id) ON DELETE CASCADE,
    category_id UUID REFERENCES categories (category_id) ON DELETE SET NULL,
    supplier_id UUID REFERENCES suppliers (supplier_id) ON DELETE SET NULL,
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(128) NOT NULL,
    sku_root VARCHAR(128) NOT NULL DEFAULT '',
    brand VARCHAR(128) NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    image_url VARCHAR(512) NOT NULL DEFAULT '',
    status VARCHAR(32) NOT NULL DEFAULT 'draft',
    default_price_amount NUMERIC(12, 2) NOT NULL DEFAULT 0,
    min_price_amount NUMERIC(12, 2) NOT NULL DEFAULT 0,
    max_discount_percent NUMERIC(5, 2) NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (client_id, slug)
);

CREATE INDEX ix_products_client_id ON products (client_id);
CREATE INDEX ix_products_status ON products (status);

CREATE TABLE product_variants (
    variant_id UUID PRIMARY KEY,
    client_id UUID NOT NULL REFERENCES clients (client_id) ON DELETE CASCADE,
    product_id UUID NOT NULL REFERENCES products (product_id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    sku VARCHAR(128) NOT NULL,
    barcode VARCHAR(128) NOT NULL DEFAULT '',
    option_values_json JSONB,
    status VARCHAR(32) NOT NULL DEFAULT 'active',
    cost_amount NUMERIC(12, 2) NOT NULL DEFAULT 0,
    price_amount NUMERIC(12, 2) NOT NULL DEFAULT 0,
    min_price_amount NUMERIC(12, 2) NOT NULL DEFAULT 0,
    reorder_level NUMERIC(14, 3) NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (client_id, sku)
);

CREATE INDEX ix_product_variants_client_id ON product_variants (client_id);
CREATE INDEX ix_product_variants_product_id ON product_variants (product_id);
CREATE INDEX ix_product_variants_status ON product_variants (status);

CREATE TABLE purchases (
    purchase_id UUID PRIMARY KEY,
    client_id UUID NOT NULL REFERENCES clients (client_id) ON DELETE CASCADE,
    supplier_id UUID REFERENCES suppliers (supplier_id) ON DELETE SET NULL,
    location_id UUID NOT NULL REFERENCES locations (location_id),
    purchase_number VARCHAR(64) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'draft',
    ordered_at TIMESTAMPTZ,
    received_at TIMESTAMPTZ,
    notes TEXT NOT NULL DEFAULT '',
    created_by_user_id UUID REFERENCES users (user_id) ON DELETE SET NULL,
    subtotal_amount NUMERIC(12, 2) NOT NULL DEFAULT 0,
    total_amount NUMERIC(12, 2) NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (client_id, purchase_number)
);

CREATE INDEX ix_purchases_client_id ON purchases (client_id);
CREATE INDEX ix_purchases_status ON purchases (status);

CREATE TABLE purchase_items (
    purchase_item_id UUID PRIMARY KEY,
    client_id UUID NOT NULL REFERENCES clients (client_id) ON DELETE CASCADE,
    purchase_id UUID NOT NULL REFERENCES purchases (purchase_id) ON DELETE CASCADE,
    variant_id UUID NOT NULL REFERENCES product_variants (variant_id),
    quantity NUMERIC(14, 3) NOT NULL DEFAULT 0,
    received_quantity NUMERIC(14, 3) NOT NULL DEFAULT 0,
    unit_cost_amount NUMERIC(12, 2) NOT NULL DEFAULT 0,
    line_total_amount NUMERIC(12, 2) NOT NULL DEFAULT 0,
    notes TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_purchase_items_purchase_id ON purchase_items (purchase_id);

CREATE TABLE inventory_ledger (
    entry_id UUID PRIMARY KEY,
    client_id UUID NOT NULL REFERENCES clients (client_id) ON DELETE CASCADE,
    variant_id UUID NOT NULL REFERENCES product_variants (variant_id),
    location_id UUID NOT NULL REFERENCES locations (location_id),
    movement_type VARCHAR(32) NOT NULL,
    reference_type VARCHAR(64) NOT NULL,
    reference_id VARCHAR(64) NOT NULL,
    reference_line_id VARCHAR(64),
    quantity_delta NUMERIC(14, 3) NOT NULL,
    unit_cost_amount NUMERIC(12, 2),
    unit_price_amount NUMERIC(12, 2),
    reason VARCHAR(255) NOT NULL DEFAULT '',
    created_by_user_id UUID REFERENCES users (user_id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_inventory_ledger_variant_location ON inventory_ledger (client_id, variant_id, location_id);
CREATE INDEX ix_inventory_ledger_reference ON inventory_ledger (reference_type, reference_id);

CREATE TABLE customers (
    customer_id UUID PRIMARY KEY,
    client_id UUID NOT NULL REFERENCES clients (client_id) ON DELETE CASCADE,
    code VARCHAR(64) NOT NULL,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL DEFAULT '',
    phone VARCHAR(64) NOT NULL DEFAULT '',
    whatsapp_number VARCHAR(64) NOT NULL DEFAULT '',
    address TEXT NOT NULL DEFAULT '',
    status VARCHAR(32) NOT NULL DEFAULT 'active',
    notes TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (client_id, code)
);

CREATE INDEX ix_customers_client_id ON customers (client_id);
CREATE INDEX ix_customers_status ON customers (status);

CREATE TABLE sales_orders (
    sales_order_id UUID PRIMARY KEY,
    client_id UUID NOT NULL REFERENCES clients (client_id) ON DELETE CASCADE,
    customer_id UUID REFERENCES customers (customer_id) ON DELETE SET NULL,
    location_id UUID NOT NULL REFERENCES locations (location_id),
    order_number VARCHAR(64) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'draft',
    payment_status VARCHAR(32) NOT NULL DEFAULT 'unpaid',
    shipment_status VARCHAR(32) NOT NULL DEFAULT 'pending',
    ordered_at TIMESTAMPTZ,
    confirmed_at TIMESTAMPTZ,
    notes TEXT NOT NULL DEFAULT '',
    created_by_user_id UUID REFERENCES users (user_id) ON DELETE SET NULL,
    subtotal_amount NUMERIC(12, 2) NOT NULL DEFAULT 0,
    discount_amount NUMERIC(12, 2) NOT NULL DEFAULT 0,
    total_amount NUMERIC(12, 2) NOT NULL DEFAULT 0,
    paid_amount NUMERIC(12, 2) NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (client_id, order_number)
);

CREATE INDEX ix_sales_orders_client_id ON sales_orders (client_id);
CREATE INDEX ix_sales_orders_status ON sales_orders (status);
CREATE INDEX ix_sales_orders_payment_status ON sales_orders (payment_status);
CREATE INDEX ix_sales_orders_shipment_status ON sales_orders (shipment_status);

CREATE TABLE sales_order_items (
    sales_order_item_id UUID PRIMARY KEY,
    client_id UUID NOT NULL REFERENCES clients (client_id) ON DELETE CASCADE,
    sales_order_id UUID NOT NULL REFERENCES sales_orders (sales_order_id) ON DELETE CASCADE,
    variant_id UUID NOT NULL REFERENCES product_variants (variant_id),
    quantity NUMERIC(14, 3) NOT NULL DEFAULT 0,
    unit_price_amount NUMERIC(12, 2) NOT NULL DEFAULT 0,
    discount_amount NUMERIC(12, 2) NOT NULL DEFAULT 0,
    line_total_amount NUMERIC(12, 2) NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_sales_order_items_order_id ON sales_order_items (sales_order_id);

CREATE TABLE sales_returns (
    sales_return_id UUID PRIMARY KEY,
    client_id UUID NOT NULL REFERENCES clients (client_id) ON DELETE CASCADE,
    sales_order_id UUID REFERENCES sales_orders (sales_order_id) ON DELETE SET NULL,
    customer_id UUID REFERENCES customers (customer_id) ON DELETE SET NULL,
    return_number VARCHAR(64) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'pending',
    refund_status VARCHAR(32) NOT NULL DEFAULT 'pending',
    requested_at TIMESTAMPTZ,
    approved_at TIMESTAMPTZ,
    received_at TIMESTAMPTZ,
    notes TEXT NOT NULL DEFAULT '',
    created_by_user_id UUID REFERENCES users (user_id) ON DELETE SET NULL,
    subtotal_amount NUMERIC(12, 2) NOT NULL DEFAULT 0,
    refund_amount NUMERIC(12, 2) NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (client_id, return_number)
);

CREATE INDEX ix_sales_returns_client_id ON sales_returns (client_id);
CREATE INDEX ix_sales_returns_status ON sales_returns (status);
CREATE INDEX ix_sales_returns_refund_status ON sales_returns (refund_status);

CREATE TABLE sales_return_items (
    sales_return_item_id UUID PRIMARY KEY,
    client_id UUID NOT NULL REFERENCES clients (client_id) ON DELETE CASCADE,
    sales_return_id UUID NOT NULL REFERENCES sales_returns (sales_return_id) ON DELETE CASCADE,
    sales_order_item_id UUID REFERENCES sales_order_items (sales_order_item_id) ON DELETE SET NULL,
    variant_id UUID NOT NULL REFERENCES product_variants (variant_id),
    quantity NUMERIC(14, 3) NOT NULL DEFAULT 0,
    restock_quantity NUMERIC(14, 3) NOT NULL DEFAULT 0,
    unit_refund_amount NUMERIC(12, 2) NOT NULL DEFAULT 0,
    disposition VARCHAR(64) NOT NULL DEFAULT 'restock',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_sales_return_items_return_id ON sales_return_items (sales_return_id);

CREATE TABLE payments (
    payment_id UUID PRIMARY KEY,
    client_id UUID NOT NULL REFERENCES clients (client_id) ON DELETE CASCADE,
    sales_order_id UUID REFERENCES sales_orders (sales_order_id) ON DELETE SET NULL,
    sales_return_id UUID REFERENCES sales_returns (sales_return_id) ON DELETE SET NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'pending',
    method VARCHAR(64) NOT NULL DEFAULT 'manual',
    amount NUMERIC(12, 2) NOT NULL DEFAULT 0,
    paid_at TIMESTAMPTZ,
    reference VARCHAR(128) NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    created_by_user_id UUID REFERENCES users (user_id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_payments_client_id ON payments (client_id);
CREATE INDEX ix_payments_status ON payments (status);

CREATE TABLE shipments (
    shipment_id UUID PRIMARY KEY,
    client_id UUID NOT NULL REFERENCES clients (client_id) ON DELETE CASCADE,
    sales_order_id UUID NOT NULL REFERENCES sales_orders (sales_order_id) ON DELETE CASCADE,
    status VARCHAR(32) NOT NULL DEFAULT 'pending',
    tracking_number VARCHAR(128) NOT NULL DEFAULT '',
    carrier VARCHAR(128) NOT NULL DEFAULT '',
    shipped_at TIMESTAMPTZ,
    delivered_at TIMESTAMPTZ,
    failed_at TIMESTAMPTZ,
    notes TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_shipments_client_id ON shipments (client_id);
CREATE INDEX ix_shipments_status ON shipments (status);

CREATE TABLE refunds (
    refund_id UUID PRIMARY KEY,
    client_id UUID NOT NULL REFERENCES clients (client_id) ON DELETE CASCADE,
    sales_return_id UUID NOT NULL REFERENCES sales_returns (sales_return_id) ON DELETE CASCADE,
    payment_id UUID REFERENCES payments (payment_id) ON DELETE SET NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'pending',
    amount NUMERIC(12, 2) NOT NULL DEFAULT 0,
    refunded_at TIMESTAMPTZ,
    reason TEXT NOT NULL DEFAULT '',
    created_by_user_id UUID REFERENCES users (user_id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_refunds_client_id ON refunds (client_id);
CREATE INDEX ix_refunds_status ON refunds (status);

CREATE TABLE expenses (
    expense_id UUID PRIMARY KEY,
    client_id UUID NOT NULL REFERENCES clients (client_id) ON DELETE CASCADE,
    expense_number VARCHAR(64) NOT NULL,
    category VARCHAR(64) NOT NULL DEFAULT 'general',
    description TEXT NOT NULL DEFAULT '',
    vendor_name VARCHAR(255) NOT NULL DEFAULT '',
    amount NUMERIC(12, 2) NOT NULL DEFAULT 0,
    incurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    payment_status VARCHAR(32) NOT NULL DEFAULT 'unpaid',
    created_by_user_id UUID REFERENCES users (user_id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (client_id, expense_number)
);

CREATE INDEX ix_expenses_client_id ON expenses (client_id);
CREATE INDEX ix_expenses_payment_status ON expenses (payment_status);

COMMIT;
