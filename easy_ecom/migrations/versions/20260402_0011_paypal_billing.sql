ALTER TABLE billing_plans
    ADD COLUMN IF NOT EXISTS billing_provider VARCHAR(32) NOT NULL DEFAULT 'paypal',
    ADD COLUMN IF NOT EXISTS provider_product_id VARCHAR(128) NULL,
    ADD COLUMN IF NOT EXISTS provider_plan_id VARCHAR(128) NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_billing_plans_provider_product_id
    ON billing_plans (provider_product_id) WHERE provider_product_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_billing_plans_provider_plan_id
    ON billing_plans (provider_plan_id) WHERE provider_plan_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_billing_plans_billing_provider ON billing_plans (billing_provider);

ALTER TABLE billing_customers
    ADD COLUMN IF NOT EXISTS billing_provider VARCHAR(32) NOT NULL DEFAULT 'paypal',
    ADD COLUMN IF NOT EXISTS provider_customer_id VARCHAR(128) NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_billing_customers_provider_customer_id
    ON billing_customers (provider_customer_id) WHERE provider_customer_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_billing_customers_billing_provider ON billing_customers (billing_provider);

ALTER TABLE subscriptions
    ADD COLUMN IF NOT EXISTS billing_provider VARCHAR(32) NOT NULL DEFAULT 'paypal',
    ADD COLUMN IF NOT EXISTS provider_subscription_id VARCHAR(128) NULL,
    ADD COLUMN IF NOT EXISTS provider_customer_id VARCHAR(128) NULL,
    ADD COLUMN IF NOT EXISTS provider_plan_id VARCHAR(128) NULL,
    ADD COLUMN IF NOT EXISTS cancel_effective_at TIMESTAMPTZ NULL,
    ADD COLUMN IF NOT EXISTS pending_plan_code VARCHAR(32) NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_subscriptions_provider_subscription_id
    ON subscriptions (provider_subscription_id) WHERE provider_subscription_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_subscriptions_billing_provider ON subscriptions (billing_provider);
CREATE INDEX IF NOT EXISTS ix_subscriptions_provider_customer_id ON subscriptions (provider_customer_id);
CREATE INDEX IF NOT EXISTS ix_subscriptions_provider_plan_id ON subscriptions (provider_plan_id);

ALTER TABLE payment_events
    ADD COLUMN IF NOT EXISTS billing_provider VARCHAR(32) NOT NULL DEFAULT 'paypal',
    ADD COLUMN IF NOT EXISTS provider_event_id VARCHAR(128) NULL,
    ADD COLUMN IF NOT EXISTS provider_object_id VARCHAR(128) NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_payment_events_provider_event_id
    ON payment_events (provider_event_id) WHERE provider_event_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_payment_events_billing_provider ON payment_events (billing_provider);
CREATE INDEX IF NOT EXISTS ix_payment_events_provider_object_id ON payment_events (provider_object_id);

UPDATE billing_plans
SET billing_provider = COALESCE(NULLIF(TRIM(billing_provider), ''), 'paypal');

UPDATE billing_customers
SET billing_provider = COALESCE(NULLIF(TRIM(billing_provider), ''), 'paypal');

UPDATE subscriptions
SET billing_provider = COALESCE(NULLIF(TRIM(billing_provider), ''), 'paypal');

UPDATE payment_events
SET billing_provider = COALESCE(NULLIF(TRIM(billing_provider), ''), 'paypal');
