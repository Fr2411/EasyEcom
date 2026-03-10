BEGIN;

CREATE TABLE IF NOT EXISTS sales_orders (
  order_id VARCHAR(64) PRIMARY KEY,
  client_id VARCHAR(64) NOT NULL,
  sale_no VARCHAR(64) NOT NULL,
  timestamp VARCHAR(64) NOT NULL DEFAULT '',
  customer_id VARCHAR(64) NOT NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'confirmed',
  subtotal VARCHAR(64) NOT NULL DEFAULT '0',
  discount VARCHAR(64) NOT NULL DEFAULT '0',
  tax VARCHAR(64) NOT NULL DEFAULT '0',
  grand_total VARCHAR(64) NOT NULL DEFAULT '0',
  note TEXT NOT NULL DEFAULT '',
  created_by_user_id VARCHAR(64) NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_sales_orders_client_id ON sales_orders(client_id);
CREATE INDEX IF NOT EXISTS idx_sales_orders_client_sale_no ON sales_orders(client_id, sale_no);
CREATE INDEX IF NOT EXISTS idx_sales_orders_client_customer_id ON sales_orders(client_id, customer_id);

CREATE TABLE IF NOT EXISTS sales_order_items (
  order_item_id VARCHAR(64) PRIMARY KEY,
  order_id VARCHAR(64) NOT NULL,
  client_id VARCHAR(64) NOT NULL,
  product_id VARCHAR(64) NOT NULL,
  product_name_snapshot VARCHAR(255) NOT NULL DEFAULT '',
  qty VARCHAR(64) NOT NULL DEFAULT '0',
  unit_selling_price VARCHAR(64) NOT NULL DEFAULT '0',
  total_selling_price VARCHAR(64) NOT NULL DEFAULT '0'
);

CREATE INDEX IF NOT EXISTS idx_sales_order_items_client_order ON sales_order_items(client_id, order_id);
CREATE INDEX IF NOT EXISTS idx_sales_order_items_client_product ON sales_order_items(client_id, product_id);

COMMIT;
