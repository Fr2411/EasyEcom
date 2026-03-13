BEGIN;

ALTER TABLE product_variants
    ADD COLUMN IF NOT EXISTS default_purchase_price VARCHAR(64) NOT NULL DEFAULT '0';

UPDATE product_variants
SET default_purchase_price = '0'
WHERE COALESCE(default_purchase_price, '') = '';

COMMIT;
