BEGIN;

CREATE TABLE IF NOT EXISTS sales_returns (
  return_id VARCHAR(64) PRIMARY KEY,
  client_id VARCHAR(64) NOT NULL,
  return_no VARCHAR(64) NOT NULL DEFAULT '',
  sale_id VARCHAR(64) NOT NULL,
  sale_no VARCHAR(64) NOT NULL DEFAULT '',
  customer_id VARCHAR(64) NOT NULL,
  reason VARCHAR(255) NOT NULL DEFAULT '',
  note TEXT NOT NULL DEFAULT '',
  return_total VARCHAR(64) NOT NULL DEFAULT '0',
  created_at VARCHAR(64) NOT NULL DEFAULT '',
  created_by_user_id VARCHAR(64) NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS sales_return_items (
  return_item_id VARCHAR(64) PRIMARY KEY,
  return_id VARCHAR(64) NOT NULL,
  client_id VARCHAR(64) NOT NULL,
  sale_item_id VARCHAR(64) NOT NULL,
  product_id VARCHAR(64) NOT NULL,
  product_name_snapshot VARCHAR(255) NOT NULL DEFAULT '',
  sold_qty VARCHAR(64) NOT NULL DEFAULT '0',
  return_qty VARCHAR(64) NOT NULL DEFAULT '0',
  unit_price VARCHAR(64) NOT NULL DEFAULT '0',
  line_total VARCHAR(64) NOT NULL DEFAULT '0',
  reason VARCHAR(255) NOT NULL DEFAULT '',
  condition_status VARCHAR(64) NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_sales_returns_client_created_at ON sales_returns(client_id, created_at);
CREATE INDEX IF NOT EXISTS idx_sales_returns_client_return_no ON sales_returns(client_id, return_no);
CREATE INDEX IF NOT EXISTS idx_sales_returns_client_sale_no ON sales_returns(client_id, sale_no);
CREATE INDEX IF NOT EXISTS idx_sales_return_items_return_id ON sales_return_items(return_id);
CREATE INDEX IF NOT EXISTS idx_sales_return_items_client_sale_item ON sales_return_items(client_id, sale_item_id);

COMMIT;
