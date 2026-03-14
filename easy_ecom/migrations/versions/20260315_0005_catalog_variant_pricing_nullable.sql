ALTER TABLE products
    ALTER COLUMN default_price_amount DROP NOT NULL,
    ALTER COLUMN default_price_amount DROP DEFAULT,
    ALTER COLUMN min_price_amount DROP NOT NULL,
    ALTER COLUMN min_price_amount DROP DEFAULT,
    ALTER COLUMN max_discount_percent DROP NOT NULL,
    ALTER COLUMN max_discount_percent DROP DEFAULT;

ALTER TABLE product_variants
    ALTER COLUMN cost_amount DROP NOT NULL,
    ALTER COLUMN cost_amount DROP DEFAULT,
    ALTER COLUMN price_amount DROP NOT NULL,
    ALTER COLUMN price_amount DROP DEFAULT,
    ALTER COLUMN min_price_amount DROP NOT NULL,
    ALTER COLUMN min_price_amount DROP DEFAULT;
