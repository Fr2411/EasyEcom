BEGIN;

ALTER TABLE payments
    ADD COLUMN IF NOT EXISTS direction VARCHAR(8) NOT NULL DEFAULT 'in';

UPDATE payments
SET direction = CASE
    WHEN sales_return_id IS NOT NULL THEN 'out'
    ELSE 'in'
END;

CREATE INDEX IF NOT EXISTS ix_payments_direction ON payments (direction);

COMMIT;
