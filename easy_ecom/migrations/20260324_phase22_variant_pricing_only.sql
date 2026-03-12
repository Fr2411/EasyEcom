BEGIN;

-- Enforce variant-only pricing ownership for Products & Stock.
ALTER TABLE products DROP COLUMN IF EXISTS default_selling_price;
ALTER TABLE products DROP COLUMN IF EXISTS max_discount_pct;

COMMIT;
