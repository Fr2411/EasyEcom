BEGIN;

-- Ensure parent tables expose composite unique keys required for tenant-safe FK targets.
ALTER TABLE categories ADD CONSTRAINT uq_categories_client_category_id UNIQUE (client_id, category_id);
ALTER TABLE suppliers ADD CONSTRAINT uq_suppliers_client_supplier_id UNIQUE (client_id, supplier_id);
ALTER TABLE products ADD CONSTRAINT uq_products_client_product_id UNIQUE (client_id, product_id);
ALTER TABLE product_variants ADD CONSTRAINT uq_product_variants_client_variant_id UNIQUE (client_id, variant_id);
ALTER TABLE locations ADD CONSTRAINT uq_locations_client_location_id UNIQUE (client_id, location_id);
ALTER TABLE users ADD CONSTRAINT uq_users_client_user_id UNIQUE (client_id, user_id);
ALTER TABLE purchases ADD CONSTRAINT uq_purchases_client_purchase_id UNIQUE (client_id, purchase_id);
ALTER TABLE customers ADD CONSTRAINT uq_customers_client_customer_id UNIQUE (client_id, customer_id);
ALTER TABLE sales_orders ADD CONSTRAINT uq_sales_orders_client_sales_order_id UNIQUE (client_id, sales_order_id);
ALTER TABLE sales_order_items ADD CONSTRAINT uq_sales_order_items_client_sales_order_item_id UNIQUE (client_id, sales_order_item_id);
ALTER TABLE sales_returns ADD CONSTRAINT uq_sales_returns_client_sales_return_id UNIQUE (client_id, sales_return_id);
ALTER TABLE payments ADD CONSTRAINT uq_payments_client_payment_id UNIQUE (client_id, payment_id);

-- Preflight mismatch checks prevent partially-applied FK rewrites with invalid historical data.
DO $$
DECLARE
    mismatch_count BIGINT;
BEGIN
    SELECT COUNT(*) INTO mismatch_count
    FROM products p
    JOIN categories c ON c.category_id = p.category_id
    WHERE p.category_id IS NOT NULL
      AND p.client_id <> c.client_id;
    IF mismatch_count > 0 THEN
        RAISE EXCEPTION 'Tenant mismatch: products.category_id -> categories (% rows)', mismatch_count;
    END IF;

    SELECT COUNT(*) INTO mismatch_count
    FROM products p
    JOIN suppliers s ON s.supplier_id = p.supplier_id
    WHERE p.supplier_id IS NOT NULL
      AND p.client_id <> s.client_id;
    IF mismatch_count > 0 THEN
        RAISE EXCEPTION 'Tenant mismatch: products.supplier_id -> suppliers (% rows)', mismatch_count;
    END IF;

    SELECT COUNT(*) INTO mismatch_count
    FROM product_variants v
    JOIN products p ON p.product_id = v.product_id
    WHERE v.client_id <> p.client_id;
    IF mismatch_count > 0 THEN
        RAISE EXCEPTION 'Tenant mismatch: product_variants.product_id -> products (% rows)', mismatch_count;
    END IF;

    SELECT COUNT(*) INTO mismatch_count
    FROM purchases p
    JOIN suppliers s ON s.supplier_id = p.supplier_id
    WHERE p.supplier_id IS NOT NULL
      AND p.client_id <> s.client_id;
    IF mismatch_count > 0 THEN
        RAISE EXCEPTION 'Tenant mismatch: purchases.supplier_id -> suppliers (% rows)', mismatch_count;
    END IF;

    SELECT COUNT(*) INTO mismatch_count
    FROM purchases p
    JOIN locations l ON l.location_id = p.location_id
    WHERE p.client_id <> l.client_id;
    IF mismatch_count > 0 THEN
        RAISE EXCEPTION 'Tenant mismatch: purchases.location_id -> locations (% rows)', mismatch_count;
    END IF;

    SELECT COUNT(*) INTO mismatch_count
    FROM purchases p
    JOIN users u ON u.user_id = p.created_by_user_id
    WHERE p.created_by_user_id IS NOT NULL
      AND p.client_id <> u.client_id;
    IF mismatch_count > 0 THEN
        RAISE EXCEPTION 'Tenant mismatch: purchases.created_by_user_id -> users (% rows)', mismatch_count;
    END IF;

    SELECT COUNT(*) INTO mismatch_count
    FROM purchase_items pi
    JOIN purchases p ON p.purchase_id = pi.purchase_id
    WHERE pi.client_id <> p.client_id;
    IF mismatch_count > 0 THEN
        RAISE EXCEPTION 'Tenant mismatch: purchase_items.purchase_id -> purchases (% rows)', mismatch_count;
    END IF;

    SELECT COUNT(*) INTO mismatch_count
    FROM purchase_items pi
    JOIN product_variants v ON v.variant_id = pi.variant_id
    WHERE pi.client_id <> v.client_id;
    IF mismatch_count > 0 THEN
        RAISE EXCEPTION 'Tenant mismatch: purchase_items.variant_id -> product_variants (% rows)', mismatch_count;
    END IF;

    SELECT COUNT(*) INTO mismatch_count
    FROM inventory_ledger il
    JOIN product_variants v ON v.variant_id = il.variant_id
    WHERE il.client_id <> v.client_id;
    IF mismatch_count > 0 THEN
        RAISE EXCEPTION 'Tenant mismatch: inventory_ledger.variant_id -> product_variants (% rows)', mismatch_count;
    END IF;

    SELECT COUNT(*) INTO mismatch_count
    FROM inventory_ledger il
    JOIN locations l ON l.location_id = il.location_id
    WHERE il.client_id <> l.client_id;
    IF mismatch_count > 0 THEN
        RAISE EXCEPTION 'Tenant mismatch: inventory_ledger.location_id -> locations (% rows)', mismatch_count;
    END IF;

    SELECT COUNT(*) INTO mismatch_count
    FROM inventory_ledger il
    JOIN users u ON u.user_id = il.created_by_user_id
    WHERE il.created_by_user_id IS NOT NULL
      AND il.client_id <> u.client_id;
    IF mismatch_count > 0 THEN
        RAISE EXCEPTION 'Tenant mismatch: inventory_ledger.created_by_user_id -> users (% rows)', mismatch_count;
    END IF;

    SELECT COUNT(*) INTO mismatch_count
    FROM sales_orders so
    JOIN customers c ON c.customer_id = so.customer_id
    WHERE so.customer_id IS NOT NULL
      AND so.client_id <> c.client_id;
    IF mismatch_count > 0 THEN
        RAISE EXCEPTION 'Tenant mismatch: sales_orders.customer_id -> customers (% rows)', mismatch_count;
    END IF;

    SELECT COUNT(*) INTO mismatch_count
    FROM sales_orders so
    JOIN locations l ON l.location_id = so.location_id
    WHERE so.client_id <> l.client_id;
    IF mismatch_count > 0 THEN
        RAISE EXCEPTION 'Tenant mismatch: sales_orders.location_id -> locations (% rows)', mismatch_count;
    END IF;

    SELECT COUNT(*) INTO mismatch_count
    FROM sales_orders so
    JOIN users u ON u.user_id = so.created_by_user_id
    WHERE so.created_by_user_id IS NOT NULL
      AND so.client_id <> u.client_id;
    IF mismatch_count > 0 THEN
        RAISE EXCEPTION 'Tenant mismatch: sales_orders.created_by_user_id -> users (% rows)', mismatch_count;
    END IF;

    SELECT COUNT(*) INTO mismatch_count
    FROM sales_order_items soi
    JOIN sales_orders so ON so.sales_order_id = soi.sales_order_id
    WHERE soi.client_id <> so.client_id;
    IF mismatch_count > 0 THEN
        RAISE EXCEPTION 'Tenant mismatch: sales_order_items.sales_order_id -> sales_orders (% rows)', mismatch_count;
    END IF;

    SELECT COUNT(*) INTO mismatch_count
    FROM sales_order_items soi
    JOIN product_variants v ON v.variant_id = soi.variant_id
    WHERE soi.client_id <> v.client_id;
    IF mismatch_count > 0 THEN
        RAISE EXCEPTION 'Tenant mismatch: sales_order_items.variant_id -> product_variants (% rows)', mismatch_count;
    END IF;

    SELECT COUNT(*) INTO mismatch_count
    FROM sales_returns sr
    JOIN sales_orders so ON so.sales_order_id = sr.sales_order_id
    WHERE sr.sales_order_id IS NOT NULL
      AND sr.client_id <> so.client_id;
    IF mismatch_count > 0 THEN
        RAISE EXCEPTION 'Tenant mismatch: sales_returns.sales_order_id -> sales_orders (% rows)', mismatch_count;
    END IF;

    SELECT COUNT(*) INTO mismatch_count
    FROM sales_returns sr
    JOIN customers c ON c.customer_id = sr.customer_id
    WHERE sr.customer_id IS NOT NULL
      AND sr.client_id <> c.client_id;
    IF mismatch_count > 0 THEN
        RAISE EXCEPTION 'Tenant mismatch: sales_returns.customer_id -> customers (% rows)', mismatch_count;
    END IF;

    SELECT COUNT(*) INTO mismatch_count
    FROM sales_returns sr
    JOIN users u ON u.user_id = sr.created_by_user_id
    WHERE sr.created_by_user_id IS NOT NULL
      AND sr.client_id <> u.client_id;
    IF mismatch_count > 0 THEN
        RAISE EXCEPTION 'Tenant mismatch: sales_returns.created_by_user_id -> users (% rows)', mismatch_count;
    END IF;

    SELECT COUNT(*) INTO mismatch_count
    FROM sales_return_items sri
    JOIN sales_returns sr ON sr.sales_return_id = sri.sales_return_id
    WHERE sri.client_id <> sr.client_id;
    IF mismatch_count > 0 THEN
        RAISE EXCEPTION 'Tenant mismatch: sales_return_items.sales_return_id -> sales_returns (% rows)', mismatch_count;
    END IF;

    SELECT COUNT(*) INTO mismatch_count
    FROM sales_return_items sri
    JOIN sales_order_items soi ON soi.sales_order_item_id = sri.sales_order_item_id
    WHERE sri.sales_order_item_id IS NOT NULL
      AND sri.client_id <> soi.client_id;
    IF mismatch_count > 0 THEN
        RAISE EXCEPTION 'Tenant mismatch: sales_return_items.sales_order_item_id -> sales_order_items (% rows)', mismatch_count;
    END IF;

    SELECT COUNT(*) INTO mismatch_count
    FROM sales_return_items sri
    JOIN product_variants v ON v.variant_id = sri.variant_id
    WHERE sri.client_id <> v.client_id;
    IF mismatch_count > 0 THEN
        RAISE EXCEPTION 'Tenant mismatch: sales_return_items.variant_id -> product_variants (% rows)', mismatch_count;
    END IF;

    SELECT COUNT(*) INTO mismatch_count
    FROM payments p
    JOIN sales_orders so ON so.sales_order_id = p.sales_order_id
    WHERE p.sales_order_id IS NOT NULL
      AND p.client_id <> so.client_id;
    IF mismatch_count > 0 THEN
        RAISE EXCEPTION 'Tenant mismatch: payments.sales_order_id -> sales_orders (% rows)', mismatch_count;
    END IF;

    SELECT COUNT(*) INTO mismatch_count
    FROM payments p
    JOIN sales_returns sr ON sr.sales_return_id = p.sales_return_id
    WHERE p.sales_return_id IS NOT NULL
      AND p.client_id <> sr.client_id;
    IF mismatch_count > 0 THEN
        RAISE EXCEPTION 'Tenant mismatch: payments.sales_return_id -> sales_returns (% rows)', mismatch_count;
    END IF;

    SELECT COUNT(*) INTO mismatch_count
    FROM payments p
    JOIN users u ON u.user_id = p.created_by_user_id
    WHERE p.created_by_user_id IS NOT NULL
      AND p.client_id <> u.client_id;
    IF mismatch_count > 0 THEN
        RAISE EXCEPTION 'Tenant mismatch: payments.created_by_user_id -> users (% rows)', mismatch_count;
    END IF;

    SELECT COUNT(*) INTO mismatch_count
    FROM shipments s
    JOIN sales_orders so ON so.sales_order_id = s.sales_order_id
    WHERE s.client_id <> so.client_id;
    IF mismatch_count > 0 THEN
        RAISE EXCEPTION 'Tenant mismatch: shipments.sales_order_id -> sales_orders (% rows)', mismatch_count;
    END IF;

    SELECT COUNT(*) INTO mismatch_count
    FROM refunds r
    JOIN sales_returns sr ON sr.sales_return_id = r.sales_return_id
    WHERE r.client_id <> sr.client_id;
    IF mismatch_count > 0 THEN
        RAISE EXCEPTION 'Tenant mismatch: refunds.sales_return_id -> sales_returns (% rows)', mismatch_count;
    END IF;

    SELECT COUNT(*) INTO mismatch_count
    FROM refunds r
    JOIN payments p ON p.payment_id = r.payment_id
    WHERE r.payment_id IS NOT NULL
      AND r.client_id <> p.client_id;
    IF mismatch_count > 0 THEN
        RAISE EXCEPTION 'Tenant mismatch: refunds.payment_id -> payments (% rows)', mismatch_count;
    END IF;

    SELECT COUNT(*) INTO mismatch_count
    FROM refunds r
    JOIN users u ON u.user_id = r.created_by_user_id
    WHERE r.created_by_user_id IS NOT NULL
      AND r.client_id <> u.client_id;
    IF mismatch_count > 0 THEN
        RAISE EXCEPTION 'Tenant mismatch: refunds.created_by_user_id -> users (% rows)', mismatch_count;
    END IF;

    SELECT COUNT(*) INTO mismatch_count
    FROM expenses e
    JOIN users u ON u.user_id = e.created_by_user_id
    WHERE e.created_by_user_id IS NOT NULL
      AND e.client_id <> u.client_id;
    IF mismatch_count > 0 THEN
        RAISE EXCEPTION 'Tenant mismatch: expenses.created_by_user_id -> users (% rows)', mismatch_count;
    END IF;
END $$;

ALTER TABLE products DROP CONSTRAINT IF EXISTS products_category_id_fkey;
ALTER TABLE products DROP CONSTRAINT IF EXISTS products_supplier_id_fkey;
ALTER TABLE products
    ADD CONSTRAINT fk_products_client_category
    FOREIGN KEY (client_id, category_id)
    REFERENCES categories (client_id, category_id);
ALTER TABLE products
    ADD CONSTRAINT fk_products_category_set_null
    FOREIGN KEY (category_id)
    REFERENCES categories (category_id)
    ON DELETE SET NULL;
ALTER TABLE products
    ADD CONSTRAINT fk_products_client_supplier
    FOREIGN KEY (client_id, supplier_id)
    REFERENCES suppliers (client_id, supplier_id);
ALTER TABLE products
    ADD CONSTRAINT fk_products_supplier_set_null
    FOREIGN KEY (supplier_id)
    REFERENCES suppliers (supplier_id)
    ON DELETE SET NULL;

ALTER TABLE product_variants DROP CONSTRAINT IF EXISTS product_variants_product_id_fkey;
ALTER TABLE product_variants
    ADD CONSTRAINT fk_product_variants_client_product
    FOREIGN KEY (client_id, product_id)
    REFERENCES products (client_id, product_id)
    ON DELETE CASCADE;

ALTER TABLE purchases DROP CONSTRAINT IF EXISTS purchases_supplier_id_fkey;
ALTER TABLE purchases DROP CONSTRAINT IF EXISTS purchases_location_id_fkey;
ALTER TABLE purchases DROP CONSTRAINT IF EXISTS purchases_created_by_user_id_fkey;
ALTER TABLE purchases
    ADD CONSTRAINT fk_purchases_client_supplier
    FOREIGN KEY (client_id, supplier_id)
    REFERENCES suppliers (client_id, supplier_id);
ALTER TABLE purchases
    ADD CONSTRAINT fk_purchases_supplier_set_null
    FOREIGN KEY (supplier_id)
    REFERENCES suppliers (supplier_id)
    ON DELETE SET NULL;
ALTER TABLE purchases
    ADD CONSTRAINT fk_purchases_client_location
    FOREIGN KEY (client_id, location_id)
    REFERENCES locations (client_id, location_id);
ALTER TABLE purchases
    ADD CONSTRAINT fk_purchases_client_created_by_user
    FOREIGN KEY (client_id, created_by_user_id)
    REFERENCES users (client_id, user_id);
ALTER TABLE purchases
    ADD CONSTRAINT fk_purchases_created_by_user_set_null
    FOREIGN KEY (created_by_user_id)
    REFERENCES users (user_id)
    ON DELETE SET NULL;

ALTER TABLE purchase_items DROP CONSTRAINT IF EXISTS purchase_items_purchase_id_fkey;
ALTER TABLE purchase_items DROP CONSTRAINT IF EXISTS purchase_items_variant_id_fkey;
ALTER TABLE purchase_items
    ADD CONSTRAINT fk_purchase_items_client_purchase
    FOREIGN KEY (client_id, purchase_id)
    REFERENCES purchases (client_id, purchase_id)
    ON DELETE CASCADE;
ALTER TABLE purchase_items
    ADD CONSTRAINT fk_purchase_items_client_variant
    FOREIGN KEY (client_id, variant_id)
    REFERENCES product_variants (client_id, variant_id);

ALTER TABLE inventory_ledger DROP CONSTRAINT IF EXISTS inventory_ledger_variant_id_fkey;
ALTER TABLE inventory_ledger DROP CONSTRAINT IF EXISTS inventory_ledger_location_id_fkey;
ALTER TABLE inventory_ledger DROP CONSTRAINT IF EXISTS inventory_ledger_created_by_user_id_fkey;
ALTER TABLE inventory_ledger
    ADD CONSTRAINT fk_inventory_ledger_client_variant
    FOREIGN KEY (client_id, variant_id)
    REFERENCES product_variants (client_id, variant_id);
ALTER TABLE inventory_ledger
    ADD CONSTRAINT fk_inventory_ledger_client_location
    FOREIGN KEY (client_id, location_id)
    REFERENCES locations (client_id, location_id);
ALTER TABLE inventory_ledger
    ADD CONSTRAINT fk_inventory_ledger_client_created_by_user
    FOREIGN KEY (client_id, created_by_user_id)
    REFERENCES users (client_id, user_id);
ALTER TABLE inventory_ledger
    ADD CONSTRAINT fk_inventory_ledger_created_by_user_set_null
    FOREIGN KEY (created_by_user_id)
    REFERENCES users (user_id)
    ON DELETE SET NULL;

ALTER TABLE sales_orders DROP CONSTRAINT IF EXISTS sales_orders_customer_id_fkey;
ALTER TABLE sales_orders DROP CONSTRAINT IF EXISTS sales_orders_location_id_fkey;
ALTER TABLE sales_orders DROP CONSTRAINT IF EXISTS sales_orders_created_by_user_id_fkey;
ALTER TABLE sales_orders
    ADD CONSTRAINT fk_sales_orders_client_customer
    FOREIGN KEY (client_id, customer_id)
    REFERENCES customers (client_id, customer_id);
ALTER TABLE sales_orders
    ADD CONSTRAINT fk_sales_orders_customer_set_null
    FOREIGN KEY (customer_id)
    REFERENCES customers (customer_id)
    ON DELETE SET NULL;
ALTER TABLE sales_orders
    ADD CONSTRAINT fk_sales_orders_client_location
    FOREIGN KEY (client_id, location_id)
    REFERENCES locations (client_id, location_id);
ALTER TABLE sales_orders
    ADD CONSTRAINT fk_sales_orders_client_created_by_user
    FOREIGN KEY (client_id, created_by_user_id)
    REFERENCES users (client_id, user_id);
ALTER TABLE sales_orders
    ADD CONSTRAINT fk_sales_orders_created_by_user_set_null
    FOREIGN KEY (created_by_user_id)
    REFERENCES users (user_id)
    ON DELETE SET NULL;

ALTER TABLE sales_order_items DROP CONSTRAINT IF EXISTS sales_order_items_sales_order_id_fkey;
ALTER TABLE sales_order_items DROP CONSTRAINT IF EXISTS sales_order_items_variant_id_fkey;
ALTER TABLE sales_order_items
    ADD CONSTRAINT fk_sales_order_items_client_sales_order
    FOREIGN KEY (client_id, sales_order_id)
    REFERENCES sales_orders (client_id, sales_order_id)
    ON DELETE CASCADE;
ALTER TABLE sales_order_items
    ADD CONSTRAINT fk_sales_order_items_client_variant
    FOREIGN KEY (client_id, variant_id)
    REFERENCES product_variants (client_id, variant_id);

ALTER TABLE sales_returns DROP CONSTRAINT IF EXISTS sales_returns_sales_order_id_fkey;
ALTER TABLE sales_returns DROP CONSTRAINT IF EXISTS sales_returns_customer_id_fkey;
ALTER TABLE sales_returns DROP CONSTRAINT IF EXISTS sales_returns_created_by_user_id_fkey;
ALTER TABLE sales_returns
    ADD CONSTRAINT fk_sales_returns_client_sales_order
    FOREIGN KEY (client_id, sales_order_id)
    REFERENCES sales_orders (client_id, sales_order_id);
ALTER TABLE sales_returns
    ADD CONSTRAINT fk_sales_returns_sales_order_set_null
    FOREIGN KEY (sales_order_id)
    REFERENCES sales_orders (sales_order_id)
    ON DELETE SET NULL;
ALTER TABLE sales_returns
    ADD CONSTRAINT fk_sales_returns_client_customer
    FOREIGN KEY (client_id, customer_id)
    REFERENCES customers (client_id, customer_id);
ALTER TABLE sales_returns
    ADD CONSTRAINT fk_sales_returns_customer_set_null
    FOREIGN KEY (customer_id)
    REFERENCES customers (customer_id)
    ON DELETE SET NULL;
ALTER TABLE sales_returns
    ADD CONSTRAINT fk_sales_returns_client_created_by_user
    FOREIGN KEY (client_id, created_by_user_id)
    REFERENCES users (client_id, user_id);
ALTER TABLE sales_returns
    ADD CONSTRAINT fk_sales_returns_created_by_user_set_null
    FOREIGN KEY (created_by_user_id)
    REFERENCES users (user_id)
    ON DELETE SET NULL;

ALTER TABLE sales_return_items DROP CONSTRAINT IF EXISTS sales_return_items_sales_return_id_fkey;
ALTER TABLE sales_return_items DROP CONSTRAINT IF EXISTS sales_return_items_sales_order_item_id_fkey;
ALTER TABLE sales_return_items DROP CONSTRAINT IF EXISTS sales_return_items_variant_id_fkey;
ALTER TABLE sales_return_items
    ADD CONSTRAINT fk_sales_return_items_client_sales_return
    FOREIGN KEY (client_id, sales_return_id)
    REFERENCES sales_returns (client_id, sales_return_id)
    ON DELETE CASCADE;
ALTER TABLE sales_return_items
    ADD CONSTRAINT fk_sales_return_items_client_sales_order_item
    FOREIGN KEY (client_id, sales_order_item_id)
    REFERENCES sales_order_items (client_id, sales_order_item_id);
ALTER TABLE sales_return_items
    ADD CONSTRAINT fk_sales_return_items_sales_order_item_set_null
    FOREIGN KEY (sales_order_item_id)
    REFERENCES sales_order_items (sales_order_item_id)
    ON DELETE SET NULL;
ALTER TABLE sales_return_items
    ADD CONSTRAINT fk_sales_return_items_client_variant
    FOREIGN KEY (client_id, variant_id)
    REFERENCES product_variants (client_id, variant_id);

ALTER TABLE payments DROP CONSTRAINT IF EXISTS payments_sales_order_id_fkey;
ALTER TABLE payments DROP CONSTRAINT IF EXISTS payments_sales_return_id_fkey;
ALTER TABLE payments DROP CONSTRAINT IF EXISTS payments_created_by_user_id_fkey;
ALTER TABLE payments
    ADD CONSTRAINT fk_payments_client_sales_order
    FOREIGN KEY (client_id, sales_order_id)
    REFERENCES sales_orders (client_id, sales_order_id);
ALTER TABLE payments
    ADD CONSTRAINT fk_payments_sales_order_set_null
    FOREIGN KEY (sales_order_id)
    REFERENCES sales_orders (sales_order_id)
    ON DELETE SET NULL;
ALTER TABLE payments
    ADD CONSTRAINT fk_payments_client_sales_return
    FOREIGN KEY (client_id, sales_return_id)
    REFERENCES sales_returns (client_id, sales_return_id);
ALTER TABLE payments
    ADD CONSTRAINT fk_payments_sales_return_set_null
    FOREIGN KEY (sales_return_id)
    REFERENCES sales_returns (sales_return_id)
    ON DELETE SET NULL;
ALTER TABLE payments
    ADD CONSTRAINT fk_payments_client_created_by_user
    FOREIGN KEY (client_id, created_by_user_id)
    REFERENCES users (client_id, user_id);
ALTER TABLE payments
    ADD CONSTRAINT fk_payments_created_by_user_set_null
    FOREIGN KEY (created_by_user_id)
    REFERENCES users (user_id)
    ON DELETE SET NULL;

ALTER TABLE shipments DROP CONSTRAINT IF EXISTS shipments_sales_order_id_fkey;
ALTER TABLE shipments
    ADD CONSTRAINT fk_shipments_client_sales_order
    FOREIGN KEY (client_id, sales_order_id)
    REFERENCES sales_orders (client_id, sales_order_id)
    ON DELETE CASCADE;

ALTER TABLE refunds DROP CONSTRAINT IF EXISTS refunds_sales_return_id_fkey;
ALTER TABLE refunds DROP CONSTRAINT IF EXISTS refunds_payment_id_fkey;
ALTER TABLE refunds DROP CONSTRAINT IF EXISTS refunds_created_by_user_id_fkey;
ALTER TABLE refunds
    ADD CONSTRAINT fk_refunds_client_sales_return
    FOREIGN KEY (client_id, sales_return_id)
    REFERENCES sales_returns (client_id, sales_return_id)
    ON DELETE CASCADE;
ALTER TABLE refunds
    ADD CONSTRAINT fk_refunds_client_payment
    FOREIGN KEY (client_id, payment_id)
    REFERENCES payments (client_id, payment_id);
ALTER TABLE refunds
    ADD CONSTRAINT fk_refunds_payment_set_null
    FOREIGN KEY (payment_id)
    REFERENCES payments (payment_id)
    ON DELETE SET NULL;
ALTER TABLE refunds
    ADD CONSTRAINT fk_refunds_client_created_by_user
    FOREIGN KEY (client_id, created_by_user_id)
    REFERENCES users (client_id, user_id);
ALTER TABLE refunds
    ADD CONSTRAINT fk_refunds_created_by_user_set_null
    FOREIGN KEY (created_by_user_id)
    REFERENCES users (user_id)
    ON DELETE SET NULL;

ALTER TABLE expenses DROP CONSTRAINT IF EXISTS expenses_created_by_user_id_fkey;
ALTER TABLE expenses
    ADD CONSTRAINT fk_expenses_client_created_by_user
    FOREIGN KEY (client_id, created_by_user_id)
    REFERENCES users (client_id, user_id);
ALTER TABLE expenses
    ADD CONSTRAINT fk_expenses_created_by_user_set_null
    FOREIGN KEY (created_by_user_id)
    REFERENCES users (user_id)
    ON DELETE SET NULL;

COMMIT;
