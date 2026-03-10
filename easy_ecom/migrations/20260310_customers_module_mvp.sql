BEGIN;

CREATE TABLE IF NOT EXISTS customers (
  customer_id VARCHAR(64) PRIMARY KEY,
  client_id VARCHAR(64) NOT NULL,
  created_at VARCHAR(64) NOT NULL DEFAULT '',
  updated_at VARCHAR(64) NOT NULL DEFAULT '',
  full_name VARCHAR(255) NOT NULL,
  phone VARCHAR(64) NOT NULL DEFAULT '',
  email VARCHAR(255) NOT NULL DEFAULT '',
  whatsapp VARCHAR(64) NOT NULL DEFAULT '',
  address_line1 VARCHAR(255) NOT NULL DEFAULT '',
  address_line2 VARCHAR(255) NOT NULL DEFAULT '',
  area VARCHAR(255) NOT NULL DEFAULT '',
  city VARCHAR(128) NOT NULL DEFAULT '',
  state VARCHAR(128) NOT NULL DEFAULT '',
  postal_code VARCHAR(32) NOT NULL DEFAULT '',
  country VARCHAR(128) NOT NULL DEFAULT '',
  preferred_contact_channel VARCHAR(32) NOT NULL DEFAULT 'phone',
  marketing_opt_in VARCHAR(8) NOT NULL DEFAULT 'false',
  tags TEXT NOT NULL DEFAULT '',
  notes TEXT NOT NULL DEFAULT '',
  is_active VARCHAR(8) NOT NULL DEFAULT 'true'
);

ALTER TABLE customers ADD COLUMN IF NOT EXISTS updated_at VARCHAR(64) NOT NULL DEFAULT '';
CREATE INDEX IF NOT EXISTS idx_customers_client_id ON customers(client_id);
CREATE INDEX IF NOT EXISTS idx_customers_client_name ON customers(client_id, full_name);

COMMIT;
