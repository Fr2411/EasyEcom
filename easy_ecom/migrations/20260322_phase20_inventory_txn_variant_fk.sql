BEGIN;

-- Phase 2: enforce tenant-safe variant referential integrity on inventory_txn
-- without breaking production on legacy dirty rows.

-- Keep referenced uniqueness explicit for FK eligibility.
CREATE UNIQUE INDEX IF NOT EXISTS uq_variants_client_variant ON product_variants(client_id, variant_id);
CREATE INDEX IF NOT EXISTS idx_inventory_txn_client_product_variant ON inventory_txn(client_id, product_id, variant_id);

-- Quarantine table for rows that still cannot satisfy FK after deterministic repair.
CREATE TABLE IF NOT EXISTS inventory_txn_variant_fk_review_queue (
    review_id VARCHAR(64) PRIMARY KEY,
    client_id VARCHAR(64) NOT NULL,
    txn_id VARCHAR(64) NOT NULL,
    product_id VARCHAR(64) NOT NULL DEFAULT '',
    variant_id VARCHAR(64) NOT NULL DEFAULT '',
    issue_type VARCHAR(64) NOT NULL,
    note TEXT NOT NULL DEFAULT '',
    created_at VARCHAR(64) NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_inventory_txn_variant_fk_review_client
    ON inventory_txn_variant_fk_review_queue(client_id, issue_type);

-- Deterministic self-heal: if a tenant has exactly one variant for the parent product,
-- map unresolved/mismatched rows to that single variant.
WITH single_variant AS (
    SELECT client_id, parent_product_id, MIN(variant_id) AS variant_id
    FROM product_variants
    GROUP BY client_id, parent_product_id
    HAVING COUNT(*) = 1
)
UPDATE inventory_txn it
SET variant_id = sv.variant_id
FROM single_variant sv
LEFT JOIN product_variants pv
       ON pv.client_id = it.client_id
      AND pv.variant_id = it.variant_id
WHERE it.client_id = sv.client_id
  AND it.product_id = sv.parent_product_id
  AND (
      COALESCE(it.variant_id, '') = ''
      OR pv.variant_id IS NULL
  );

-- Missing/blank variant identity.
INSERT INTO inventory_txn_variant_fk_review_queue (
    review_id, client_id, txn_id, product_id, variant_id, issue_type, note, created_at
)
SELECT
    md5('inventory_txn:missing_variant:' || it.txn_id),
    it.client_id,
    it.txn_id,
    it.product_id,
    COALESCE(it.variant_id, ''),
    'missing_variant_id',
    'variant_id is blank; cannot enforce inventory_txn -> product_variants FK until remediated',
    NOW()::text
FROM inventory_txn it
WHERE COALESCE(it.variant_id, '') = ''
ON CONFLICT (review_id) DO NOTHING;

-- Variant exists, but only in another tenant (tenant-isolation violation risk).
INSERT INTO inventory_txn_variant_fk_review_queue (
    review_id, client_id, txn_id, product_id, variant_id, issue_type, note, created_at
)
SELECT
    md5('inventory_txn:tenant_mismatch_variant:' || it.txn_id),
    it.client_id,
    it.txn_id,
    it.product_id,
    it.variant_id,
    'tenant_mismatch_variant_id',
    'variant_id exists for a different tenant; keep quarantined and manually remap to same-tenant variant',
    NOW()::text
FROM inventory_txn it
LEFT JOIN product_variants same_tenant
       ON same_tenant.client_id = it.client_id
      AND same_tenant.variant_id = it.variant_id
WHERE COALESCE(it.variant_id, '') <> ''
  AND same_tenant.variant_id IS NULL
  AND EXISTS (
      SELECT 1
      FROM product_variants cross_tenant
      WHERE cross_tenant.variant_id = it.variant_id
        AND cross_tenant.client_id <> it.client_id
  )
ON CONFLICT (review_id) DO NOTHING;

-- Variant does not exist in product_variants at all.
INSERT INTO inventory_txn_variant_fk_review_queue (
    review_id, client_id, txn_id, product_id, variant_id, issue_type, note, created_at
)
SELECT
    md5('inventory_txn:orphan_variant:' || it.txn_id),
    it.client_id,
    it.txn_id,
    it.product_id,
    it.variant_id,
    'orphan_variant_id',
    'variant_id not found in product_variants for any tenant; create/fix variant before FK validation',
    NOW()::text
FROM inventory_txn it
LEFT JOIN product_variants any_tenant
       ON any_tenant.variant_id = it.variant_id
WHERE COALESCE(it.variant_id, '') <> ''
  AND any_tenant.variant_id IS NULL
ON CONFLICT (review_id) DO NOTHING;

-- Add FK in NOT VALID mode to protect all new writes immediately while allowing
-- legacy violating rows to remain until cleaned.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'fk_inventory_txn_client_variant'
    ) THEN
        ALTER TABLE inventory_txn
            ADD CONSTRAINT fk_inventory_txn_client_variant
            FOREIGN KEY (client_id, variant_id)
            REFERENCES product_variants(client_id, variant_id)
            ON UPDATE CASCADE
            ON DELETE RESTRICT
            NOT VALID;
    END IF;
END $$;

-- Validate only when safe (no remaining violations).
DO $$
DECLARE
    unresolved_count BIGINT;
BEGIN
    SELECT COUNT(*)
    INTO unresolved_count
    FROM inventory_txn it
    LEFT JOIN product_variants pv
           ON pv.client_id = it.client_id
          AND pv.variant_id = it.variant_id
    WHERE COALESCE(it.variant_id, '') = ''
       OR pv.variant_id IS NULL;

    IF unresolved_count = 0 THEN
        ALTER TABLE inventory_txn VALIDATE CONSTRAINT fk_inventory_txn_client_variant;
    ELSE
        RAISE NOTICE 'fk_inventory_txn_client_variant left NOT VALID; % legacy inventory_txn rows still violate composite tenant+variant reference. Review inventory_txn_variant_fk_review_queue.', unresolved_count;
    END IF;
END $$;

COMMIT;
