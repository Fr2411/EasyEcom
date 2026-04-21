BEGIN;

ALTER TABLE customers
    ADD COLUMN IF NOT EXISTS email_normalized VARCHAR(255) NOT NULL DEFAULT '';

ALTER TABLE customers
    ADD COLUMN IF NOT EXISTS phone_normalized VARCHAR(64) NOT NULL DEFAULT '';

UPDATE customers
SET
    email_normalized = LOWER(BTRIM(COALESCE(email, ''))),
    phone_normalized = REGEXP_REPLACE(COALESCE(phone, ''), '[^0-9]+', '', 'g');

ALTER TABLE sales_order_items
    ADD COLUMN IF NOT EXISTS quantity_fulfilled NUMERIC(14, 3) NOT NULL DEFAULT 0;

ALTER TABLE sales_order_items
    ADD COLUMN IF NOT EXISTS quantity_cancelled NUMERIC(14, 3) NOT NULL DEFAULT 0;

CREATE INDEX IF NOT EXISTS ix_products_client_name ON products (client_id, name);
CREATE INDEX IF NOT EXISTS ix_product_variants_client_title ON product_variants (client_id, title);
CREATE INDEX IF NOT EXISTS ix_customers_client_phone_normalized ON customers (client_id, phone_normalized);
CREATE INDEX IF NOT EXISTS ix_customers_client_email_normalized ON customers (client_id, email_normalized);

COMMIT;
