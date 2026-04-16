BEGIN;

-- Legacy data preflight (run before this migration if needed):
-- SELECT count(*) FROM products
-- WHERE (default_price_amount IS NOT NULL AND default_price_amount < 0)
--    OR (min_price_amount IS NOT NULL AND min_price_amount < 0)
--    OR (max_discount_percent IS NOT NULL AND (max_discount_percent < 0 OR max_discount_percent > 100))
--    OR (default_price_amount IS NOT NULL AND min_price_amount IS NOT NULL AND min_price_amount > default_price_amount);
--
-- SELECT count(*) FROM product_variants
-- WHERE (cost_amount IS NOT NULL AND cost_amount < 0)
--    OR (price_amount IS NOT NULL AND price_amount < 0)
--    OR (min_price_amount IS NOT NULL AND min_price_amount < 0)
--    OR (price_amount IS NOT NULL AND min_price_amount IS NOT NULL AND min_price_amount > price_amount)
--    OR reorder_level < 0;
--
-- SELECT count(*) FROM purchase_items
-- WHERE quantity <= 0
--    OR received_quantity < 0
--    OR received_quantity > quantity
--    OR unit_cost_amount < 0
--    OR line_total_amount < 0;
--
-- SELECT count(*) FROM inventory_ledger
-- WHERE quantity_delta = 0
--    OR (unit_cost_amount IS NOT NULL AND unit_cost_amount < 0)
--    OR (unit_price_amount IS NOT NULL AND unit_price_amount < 0);
--
-- SELECT count(*) FROM sales_order_items
-- WHERE quantity <= 0
--    OR quantity_fulfilled < 0
--    OR quantity_cancelled < 0
--    OR quantity_fulfilled + quantity_cancelled > quantity
--    OR unit_price_amount < 0
--    OR discount_amount < 0
--    OR line_total_amount < 0;
--
-- SELECT count(*) FROM sales_return_items
-- WHERE quantity <= 0
--    OR restock_quantity < 0
--    OR restock_quantity > quantity
--    OR unit_refund_amount < 0;
--
-- Remediation guidance:
-- 1) Fix invalid rows using business-correct values from source documents (do not blanket-zero historical lines).
-- 2) For sales/purchase line inconsistencies, reconcile with auditable order/purchase records first.
-- 3) Re-run preflight queries; apply this migration only when every count is zero.

ALTER TABLE products
    ADD CONSTRAINT ck_products_default_price_non_negative
        CHECK (default_price_amount IS NULL OR default_price_amount >= 0),
    ADD CONSTRAINT ck_products_min_price_non_negative
        CHECK (min_price_amount IS NULL OR min_price_amount >= 0),
    ADD CONSTRAINT ck_products_max_discount_range
        CHECK (max_discount_percent IS NULL OR (max_discount_percent >= 0 AND max_discount_percent <= 100)),
    ADD CONSTRAINT ck_products_min_price_lte_default_price
        CHECK (default_price_amount IS NULL OR min_price_amount IS NULL OR min_price_amount <= default_price_amount);

ALTER TABLE product_variants
    ADD CONSTRAINT ck_product_variants_cost_non_negative
        CHECK (cost_amount IS NULL OR cost_amount >= 0),
    ADD CONSTRAINT ck_product_variants_price_non_negative
        CHECK (price_amount IS NULL OR price_amount >= 0),
    ADD CONSTRAINT ck_product_variants_min_price_non_negative
        CHECK (min_price_amount IS NULL OR min_price_amount >= 0),
    ADD CONSTRAINT ck_product_variants_min_price_lte_price
        CHECK (price_amount IS NULL OR min_price_amount IS NULL OR min_price_amount <= price_amount),
    ADD CONSTRAINT ck_product_variants_reorder_level_non_negative
        CHECK (reorder_level >= 0);

ALTER TABLE purchase_items
    ADD CONSTRAINT ck_purchase_items_quantity_positive
        CHECK (quantity > 0),
    ADD CONSTRAINT ck_purchase_items_received_quantity_range
        CHECK (received_quantity >= 0 AND received_quantity <= quantity),
    ADD CONSTRAINT ck_purchase_items_unit_cost_non_negative
        CHECK (unit_cost_amount >= 0),
    ADD CONSTRAINT ck_purchase_items_line_total_non_negative
        CHECK (line_total_amount >= 0);

ALTER TABLE inventory_ledger
    ADD CONSTRAINT ck_inventory_ledger_quantity_delta_non_zero
        CHECK (quantity_delta <> 0),
    ADD CONSTRAINT ck_inventory_ledger_unit_cost_non_negative
        CHECK (unit_cost_amount IS NULL OR unit_cost_amount >= 0),
    ADD CONSTRAINT ck_inventory_ledger_unit_price_non_negative
        CHECK (unit_price_amount IS NULL OR unit_price_amount >= 0);

ALTER TABLE sales_order_items
    ADD CONSTRAINT ck_sales_order_items_quantity_positive
        CHECK (quantity > 0),
    ADD CONSTRAINT ck_sales_order_items_quantity_fulfilled_non_negative
        CHECK (quantity_fulfilled >= 0),
    ADD CONSTRAINT ck_sales_order_items_quantity_cancelled_non_negative
        CHECK (quantity_cancelled >= 0),
    ADD CONSTRAINT ck_sales_order_items_quantity_progress_within_quantity
        CHECK (quantity_fulfilled + quantity_cancelled <= quantity),
    ADD CONSTRAINT ck_sales_order_items_unit_price_non_negative
        CHECK (unit_price_amount >= 0),
    ADD CONSTRAINT ck_sales_order_items_discount_non_negative
        CHECK (discount_amount >= 0),
    ADD CONSTRAINT ck_sales_order_items_line_total_non_negative
        CHECK (line_total_amount >= 0);

ALTER TABLE sales_return_items
    ADD CONSTRAINT ck_sales_return_items_quantity_positive
        CHECK (quantity > 0),
    ADD CONSTRAINT ck_sales_return_items_restock_quantity_range
        CHECK (restock_quantity >= 0 AND restock_quantity <= quantity),
    ADD CONSTRAINT ck_sales_return_items_unit_refund_non_negative
        CHECK (unit_refund_amount >= 0);

COMMIT;
