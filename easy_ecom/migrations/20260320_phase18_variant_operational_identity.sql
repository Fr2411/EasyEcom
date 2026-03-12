BEGIN;

ALTER TABLE product_variants ADD COLUMN IF NOT EXISTS barcode VARCHAR(128) NOT NULL DEFAULT '';
ALTER TABLE product_variants ALTER COLUMN sku_code SET NOT NULL;

CREATE TABLE IF NOT EXISTS stock_identity_review_queue (
    review_id VARCHAR(64) PRIMARY KEY,
    client_id VARCHAR(64) NOT NULL,
    table_name VARCHAR(64) NOT NULL,
    row_id VARCHAR(64) NOT NULL,
    legacy_product_id VARCHAR(64) NOT NULL DEFAULT '',
    issue_type VARCHAR(64) NOT NULL,
    note TEXT NOT NULL DEFAULT '',
    created_at VARCHAR(64) NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_stock_identity_review_client ON stock_identity_review_queue(client_id, table_name);

-- deterministic one-parent/one-variant backfill
WITH single_variant AS (
    SELECT client_id, parent_product_id, MIN(variant_id) AS variant_id
    FROM product_variants
    GROUP BY client_id, parent_product_id
    HAVING COUNT(*) = 1
)
UPDATE inventory_txn it
SET variant_id = sv.variant_id
FROM single_variant sv
WHERE it.client_id = sv.client_id
  AND it.product_id = sv.parent_product_id
  AND COALESCE(it.variant_id, '') = '';

WITH single_variant AS (
    SELECT client_id, parent_product_id, MIN(variant_id) AS variant_id
    FROM product_variants
    GROUP BY client_id, parent_product_id
    HAVING COUNT(*) = 1
)
UPDATE sales_order_items soi
SET variant_id = sv.variant_id
FROM single_variant sv
WHERE soi.client_id = sv.client_id
  AND soi.product_id = sv.parent_product_id
  AND COALESCE(soi.variant_id, '') = '';

WITH single_variant AS (
    SELECT client_id, parent_product_id, MIN(variant_id) AS variant_id
    FROM product_variants
    GROUP BY client_id, parent_product_id
    HAVING COUNT(*) = 1
)
UPDATE sales_return_items sri
SET variant_id = sv.variant_id
FROM single_variant sv
WHERE sri.client_id = sv.client_id
  AND sri.product_id = sv.parent_product_id
  AND COALESCE(sri.variant_id, '') = '';

WITH single_variant AS (
    SELECT client_id, parent_product_id, MIN(variant_id) AS variant_id
    FROM product_variants
    GROUP BY client_id, parent_product_id
    HAVING COUNT(*) = 1
)
UPDATE purchase_items pi
SET variant_id = sv.variant_id
FROM single_variant sv
WHERE pi.client_id = sv.client_id
  AND pi.product_id = sv.parent_product_id
  AND COALESCE(pi.variant_id, '') = '';

INSERT INTO stock_identity_review_queue (review_id, client_id, table_name, row_id, legacy_product_id, issue_type, note, created_at)
SELECT md5('inventory_txn:' || it.txn_id), it.client_id, 'inventory_txn', it.txn_id, it.product_id, 'ambiguous_parent_product', 'Multiple variants exist for parent product; manual mapping required', NOW()::text
FROM inventory_txn it
JOIN (
    SELECT client_id, parent_product_id
    FROM product_variants
    GROUP BY client_id, parent_product_id
    HAVING COUNT(*) > 1
) mv ON mv.client_id = it.client_id AND mv.parent_product_id = it.product_id
WHERE COALESCE(it.variant_id, '') = ''
ON CONFLICT (review_id) DO NOTHING;

INSERT INTO stock_identity_review_queue (review_id, client_id, table_name, row_id, legacy_product_id, issue_type, note, created_at)
SELECT md5('sales_order_items:' || soi.order_item_id), soi.client_id, 'sales_order_items', soi.order_item_id, soi.product_id, 'ambiguous_parent_product', 'Multiple variants exist for parent product; manual mapping required', NOW()::text
FROM sales_order_items soi
JOIN (
    SELECT client_id, parent_product_id
    FROM product_variants
    GROUP BY client_id, parent_product_id
    HAVING COUNT(*) > 1
) mv ON mv.client_id = soi.client_id AND mv.parent_product_id = soi.product_id
WHERE COALESCE(soi.variant_id, '') = ''
ON CONFLICT (review_id) DO NOTHING;

ALTER TABLE inventory_txn ADD CONSTRAINT chk_inventory_variant_required_for_stock CHECK (txn_type IN ('ADJUSTMENT_NOTE') OR COALESCE(variant_id, '') <> '');
ALTER TABLE sales_order_items ADD CONSTRAINT chk_sales_item_variant_required CHECK (COALESCE(variant_id, '') <> '');
ALTER TABLE sales_return_items ADD CONSTRAINT chk_return_item_variant_required CHECK (COALESCE(variant_id, '') <> '');
ALTER TABLE purchase_items ADD CONSTRAINT chk_purchase_item_variant_required CHECK (COALESCE(variant_id, '') <> '');

COMMIT;
