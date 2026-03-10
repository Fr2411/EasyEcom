BEGIN;

CREATE TABLE IF NOT EXISTS tenant_settings (
  client_id VARCHAR(64) PRIMARY KEY,
  timezone VARCHAR(64) NOT NULL DEFAULT 'UTC',
  tax_registration_no VARCHAR(120) NOT NULL DEFAULT '',
  low_stock_threshold VARCHAR(16) NOT NULL DEFAULT '5',
  default_payment_terms_days VARCHAR(16) NOT NULL DEFAULT '0',
  default_sales_note TEXT NOT NULL DEFAULT '',
  default_inventory_adjustment_reasons TEXT NOT NULL DEFAULT '',
  sales_prefix VARCHAR(12) NOT NULL DEFAULT 'SAL',
  returns_prefix VARCHAR(12) NOT NULL DEFAULT 'RET',
  updated_at VARCHAR(64) NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_tenant_settings_updated_at ON tenant_settings(updated_at);

COMMIT;
