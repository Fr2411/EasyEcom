BEGIN;

ALTER TABLE tenant_settings
  ADD COLUMN IF NOT EXISTS purchases_prefix VARCHAR(12) NOT NULL DEFAULT 'PUR';

CREATE TABLE IF NOT EXISTS purchases (
  purchase_id VARCHAR(64) PRIMARY KEY,
  client_id VARCHAR(64) NOT NULL,
  purchase_no VARCHAR(64) NOT NULL DEFAULT '',
  purchase_date VARCHAR(32) NOT NULL DEFAULT '',
  supplier_id VARCHAR(64) NOT NULL DEFAULT '',
  supplier_name_snapshot VARCHAR(255) NOT NULL DEFAULT '',
  reference_no VARCHAR(120) NOT NULL DEFAULT '',
  status VARCHAR(32) NOT NULL DEFAULT 'received',
  subtotal VARCHAR(64) NOT NULL DEFAULT '0',
  note TEXT NOT NULL DEFAULT '',
  created_at VARCHAR(64) NOT NULL DEFAULT '',
  created_by_user_id VARCHAR(64) NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_purchases_client_date ON purchases(client_id, purchase_date);
CREATE INDEX IF NOT EXISTS idx_purchases_client_no ON purchases(client_id, purchase_no);
CREATE INDEX IF NOT EXISTS idx_purchases_supplier_id ON purchases(client_id, supplier_id);

CREATE TABLE IF NOT EXISTS purchase_items (
  purchase_item_id VARCHAR(64) PRIMARY KEY,
  purchase_id VARCHAR(64) NOT NULL,
  client_id VARCHAR(64) NOT NULL,
  product_id VARCHAR(64) NOT NULL,
  product_name_snapshot VARCHAR(255) NOT NULL DEFAULT '',
  qty VARCHAR(64) NOT NULL DEFAULT '0',
  unit_cost VARCHAR(64) NOT NULL DEFAULT '0',
  line_total VARCHAR(64) NOT NULL DEFAULT '0'
);

CREATE INDEX IF NOT EXISTS idx_purchase_items_purchase_id ON purchase_items(purchase_id);
CREATE INDEX IF NOT EXISTS idx_purchase_items_client_purchase ON purchase_items(client_id, purchase_id);
CREATE INDEX IF NOT EXISTS idx_purchase_items_client_product ON purchase_items(client_id, product_id);

COMMIT;
