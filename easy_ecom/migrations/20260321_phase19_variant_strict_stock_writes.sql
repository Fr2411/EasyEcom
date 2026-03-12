BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'chk_inventory_txn_variant_required'
    ) THEN
        ALTER TABLE inventory_txn
            ADD CONSTRAINT chk_inventory_txn_variant_required
            CHECK (COALESCE(variant_id, '') <> '');
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'chk_purchase_item_variant_required_v2'
    ) THEN
        ALTER TABLE purchase_items
            ADD CONSTRAINT chk_purchase_item_variant_required_v2
            CHECK (COALESCE(variant_id, '') <> '');
    END IF;
END $$;

COMMIT;
