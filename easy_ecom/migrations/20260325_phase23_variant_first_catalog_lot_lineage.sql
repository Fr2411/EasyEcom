BEGIN;

ALTER TABLE product_variants
    ADD COLUMN IF NOT EXISTS default_selling_price VARCHAR(64) NOT NULL DEFAULT '0';

ALTER TABLE product_variants
    ADD COLUMN IF NOT EXISTS max_discount_pct VARCHAR(64) NOT NULL DEFAULT '0';

ALTER TABLE inventory_txn
    ADD COLUMN IF NOT EXISTS source_line_id VARCHAR(64) NOT NULL DEFAULT '';

WITH ranked_variants AS (
    SELECT
        variant_id,
        ROW_NUMBER() OVER (
            PARTITION BY client_id, parent_product_id, LOWER(COALESCE(size, '')), LOWER(COALESCE(color, '')), LOWER(COALESCE(other, ''))
            ORDER BY COALESCE(created_at, ''), variant_id
        ) AS rn
    FROM product_variants
    WHERE COALESCE(is_active, 'true') <> 'false'
)
UPDATE product_variants pv
SET is_active = 'false'
FROM ranked_variants rv
WHERE pv.variant_id = rv.variant_id
  AND rv.rn > 1;

CREATE UNIQUE INDEX IF NOT EXISTS uq_product_variants_client_parent_identity_active
    ON product_variants (
        client_id,
        parent_product_id,
        LOWER(COALESCE(size, '')),
        LOWER(COALESCE(color, '')),
        LOWER(COALESCE(other, ''))
    )
    WHERE COALESCE(is_active, 'true') <> 'false';

CREATE INDEX IF NOT EXISTS idx_inventory_txn_client_source_line
    ON inventory_txn (client_id, source_type, source_id, source_line_id);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'chk_inventory_txn_out_requires_lot_id'
    ) THEN
        ALTER TABLE inventory_txn
            ADD CONSTRAINT chk_inventory_txn_out_requires_lot_id
            CHECK (txn_type <> 'OUT' OR COALESCE(lot_id, '') <> '')
            NOT VALID;
    END IF;
END $$;

COMMIT;
