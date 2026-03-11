BEGIN;

-- 1) Add canonical variant support where stock is held at SKU level.
ALTER TABLE inventory_txn ADD COLUMN IF NOT EXISTS variant_id VARCHAR(64) NOT NULL DEFAULT '';
ALTER TABLE sales_order_items ADD COLUMN IF NOT EXISTS variant_id VARCHAR(64) NOT NULL DEFAULT '';
ALTER TABLE sales_return_items ADD COLUMN IF NOT EXISTS variant_id VARCHAR(64) NOT NULL DEFAULT '';
ALTER TABLE purchase_items ADD COLUMN IF NOT EXISTS variant_id VARCHAR(64) NOT NULL DEFAULT '';

CREATE INDEX IF NOT EXISTS idx_inventory_txn_client_variant ON inventory_txn(client_id, variant_id);
CREATE INDEX IF NOT EXISTS idx_sales_order_items_client_variant ON sales_order_items(client_id, variant_id);
CREATE INDEX IF NOT EXISTS idx_sales_return_items_client_variant ON sales_return_items(client_id, variant_id);
CREATE INDEX IF NOT EXISTS idx_purchase_items_client_variant ON purchase_items(client_id, variant_id);

-- 2) Backfill variant_id for legacy rows where product_id currently stores variant identifiers.
UPDATE sales_order_items soi
SET variant_id = pv.variant_id,
    product_id = pv.parent_product_id
FROM product_variants pv
WHERE soi.client_id = pv.client_id
  AND soi.product_id = pv.variant_id
  AND COALESCE(soi.variant_id, '') = '';

UPDATE sales_return_items sri
SET variant_id = pv.variant_id,
    product_id = pv.parent_product_id
FROM product_variants pv
WHERE sri.client_id = pv.client_id
  AND sri.product_id = pv.variant_id
  AND COALESCE(sri.variant_id, '') = '';

UPDATE purchase_items pi
SET variant_id = pv.variant_id,
    product_id = pv.parent_product_id
FROM product_variants pv
WHERE pi.client_id = pv.client_id
  AND pi.product_id = pv.variant_id
  AND COALESCE(pi.variant_id, '') = '';

UPDATE inventory_txn it
SET variant_id = pv.variant_id,
    product_id = pv.parent_product_id
FROM product_variants pv
WHERE it.client_id = pv.client_id
  AND it.product_id = pv.variant_id
  AND COALESCE(it.variant_id, '') = '';

-- 3) Tenant-safe referential integrity (composite by tenant + id).
CREATE UNIQUE INDEX IF NOT EXISTS uq_products_client_product ON products(client_id, product_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_variants_client_variant ON product_variants(client_id, variant_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_sales_orders_client_order ON sales_orders(client_id, order_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_sales_items_client_item ON sales_order_items(client_id, order_item_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_sales_returns_client_return ON sales_returns(client_id, return_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_purchase_client_purchase ON purchases(client_id, purchase_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_purchase_items_client_item ON purchase_items(client_id, purchase_item_id);

-- Orphan prevention for variants and strict tenant isolation.
ALTER TABLE product_variants
  ADD CONSTRAINT fk_product_variants_parent
  FOREIGN KEY (client_id, parent_product_id)
  REFERENCES products(client_id, product_id)
  ON UPDATE CASCADE
  ON DELETE RESTRICT;

ALTER TABLE sales_order_items
  ADD CONSTRAINT fk_sales_order_items_order
  FOREIGN KEY (client_id, order_id)
  REFERENCES sales_orders(client_id, order_id)
  ON DELETE CASCADE;

ALTER TABLE sales_return_items
  ADD CONSTRAINT fk_sales_return_items_return
  FOREIGN KEY (client_id, return_id)
  REFERENCES sales_returns(client_id, return_id)
  ON DELETE CASCADE;

ALTER TABLE purchase_items
  ADD CONSTRAINT fk_purchase_items_purchase
  FOREIGN KEY (client_id, purchase_id)
  REFERENCES purchases(client_id, purchase_id)
  ON DELETE CASCADE;

-- Inventory FK for variant_id should be enabled in a follow-up once variant_id nullability is normalized (NULL for base products).

-- 4) Strong business uniqueness constraints.
CREATE UNIQUE INDEX IF NOT EXISTS uq_sales_orders_client_sale_no ON sales_orders(client_id, sale_no);
CREATE UNIQUE INDEX IF NOT EXISTS uq_sales_returns_client_return_no ON sales_returns(client_id, return_no);
CREATE UNIQUE INDEX IF NOT EXISTS uq_purchases_client_purchase_no ON purchases(client_id, purchase_no);
CREATE UNIQUE INDEX IF NOT EXISTS uq_product_variants_client_sku_code ON product_variants(client_id, sku_code) WHERE sku_code <> '';

COMMIT;
