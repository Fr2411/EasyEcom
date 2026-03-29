ALTER TABLE clients
    ADD COLUMN IF NOT EXISTS billing_plan_code VARCHAR(32) NOT NULL DEFAULT 'free',
    ADD COLUMN IF NOT EXISTS billing_status VARCHAR(32) NOT NULL DEFAULT 'free',
    ADD COLUMN IF NOT EXISTS billing_access_state VARCHAR(32) NOT NULL DEFAULT 'free_active',
    ADD COLUMN IF NOT EXISTS billing_grace_until TIMESTAMPTZ NULL,
    ADD COLUMN IF NOT EXISTS billing_updated_at TIMESTAMPTZ NULL;

CREATE INDEX IF NOT EXISTS ix_clients_billing_plan_code ON clients (billing_plan_code);
CREATE INDEX IF NOT EXISTS ix_clients_billing_status ON clients (billing_status);
CREATE INDEX IF NOT EXISTS ix_clients_billing_access_state ON clients (billing_access_state);

CREATE TABLE IF NOT EXISTS billing_plans (
    plan_code VARCHAR(32) PRIMARY KEY,
    display_name VARCHAR(128) NOT NULL,
    is_paid BOOLEAN NOT NULL DEFAULT FALSE,
    stripe_price_id VARCHAR(128) UNIQUE NULL,
    currency_code VARCHAR(16) NOT NULL DEFAULT 'USD',
    interval VARCHAR(16) NOT NULL DEFAULT 'month',
    sort_order INTEGER NOT NULL DEFAULT 0,
    public_description TEXT NOT NULL DEFAULT '',
    feature_flags_json JSONB NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS billing_customers (
    billing_customer_id UUID PRIMARY KEY,
    client_id UUID NOT NULL REFERENCES clients(client_id) ON DELETE CASCADE,
    stripe_customer_id VARCHAR(128) NOT NULL,
    email VARCHAR(255) NOT NULL DEFAULT '',
    name VARCHAR(255) NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_billing_customers_client UNIQUE (client_id),
    CONSTRAINT uq_billing_customers_stripe_customer UNIQUE (stripe_customer_id)
);
CREATE INDEX IF NOT EXISTS ix_billing_customers_client_id ON billing_customers (client_id);

CREATE TABLE IF NOT EXISTS subscriptions (
    subscription_id UUID PRIMARY KEY,
    client_id UUID NOT NULL REFERENCES clients(client_id) ON DELETE CASCADE,
    plan_code VARCHAR(32) NOT NULL REFERENCES billing_plans(plan_code),
    stripe_subscription_id VARCHAR(128) NULL,
    stripe_customer_id VARCHAR(128) NULL,
    stripe_price_id VARCHAR(128) NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'free',
    cancel_at_period_end BOOLEAN NOT NULL DEFAULT FALSE,
    current_period_start TIMESTAMPTZ NULL,
    current_period_end TIMESTAMPTZ NULL,
    grace_until TIMESTAMPTZ NULL,
    last_invoice_id VARCHAR(128) NULL,
    last_checkout_session_id VARCHAR(128) NULL,
    updated_from_event_id VARCHAR(128) NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_subscriptions_client UNIQUE (client_id),
    CONSTRAINT uq_subscriptions_stripe_subscription UNIQUE (stripe_subscription_id)
);
CREATE INDEX IF NOT EXISTS ix_subscriptions_client_id ON subscriptions (client_id);
CREATE INDEX IF NOT EXISTS ix_subscriptions_stripe_customer_id ON subscriptions (stripe_customer_id);
CREATE INDEX IF NOT EXISTS ix_subscriptions_stripe_price_id ON subscriptions (stripe_price_id);
CREATE INDEX IF NOT EXISTS ix_subscriptions_status ON subscriptions (status);

CREATE TABLE IF NOT EXISTS payment_events (
    payment_event_id UUID PRIMARY KEY,
    client_id UUID NULL REFERENCES clients(client_id) ON DELETE CASCADE,
    stripe_event_id VARCHAR(128) NOT NULL,
    event_type VARCHAR(128) NOT NULL,
    stripe_object_id VARCHAR(128) NOT NULL DEFAULT '',
    status VARCHAR(32) NOT NULL DEFAULT 'received',
    processed_at TIMESTAMPTZ NULL,
    payload_json JSONB NULL,
    error_message TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_payment_events_stripe_event UNIQUE (stripe_event_id)
);
CREATE INDEX IF NOT EXISTS ix_payment_events_client_id ON payment_events (client_id);
CREATE INDEX IF NOT EXISTS ix_payment_events_event_type ON payment_events (event_type);
CREATE INDEX IF NOT EXISTS ix_payment_events_status ON payment_events (status);

CREATE TABLE IF NOT EXISTS usage_counters (
    usage_counter_id UUID PRIMARY KEY,
    client_id UUID NOT NULL REFERENCES clients(client_id) ON DELETE CASCADE,
    metric_code VARCHAR(64) NOT NULL,
    period_start TIMESTAMPTZ NOT NULL,
    period_end TIMESTAMPTZ NOT NULL,
    quantity INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_usage_counters_client_metric_period UNIQUE (client_id, metric_code, period_start, period_end)
);
CREATE INDEX IF NOT EXISTS ix_usage_counters_client_id ON usage_counters (client_id);
CREATE INDEX IF NOT EXISTS ix_usage_counters_metric_code ON usage_counters (metric_code);

INSERT INTO billing_plans (
    plan_code,
    display_name,
    is_paid,
    stripe_price_id,
    currency_code,
    interval,
    sort_order,
    public_description,
    feature_flags_json
)
VALUES
    ('free', 'Free', FALSE, NULL, 'USD', 'month', 1, 'Core commerce workspace for early-stage tenants.', '{"tier":"free","full_access":false}'),
    ('growth', 'Growth', TRUE, NULL, 'USD', 'month', 2, 'Full operating stack for growing businesses.', '{"tier":"growth","full_access":true}'),
    ('scale', 'Scale', TRUE, NULL, 'USD', 'month', 3, 'Advanced commercial plan for larger operators.', '{"tier":"scale","full_access":true}')
ON CONFLICT (plan_code) DO UPDATE SET
    display_name = EXCLUDED.display_name,
    is_paid = EXCLUDED.is_paid,
    currency_code = EXCLUDED.currency_code,
    interval = EXCLUDED.interval,
    sort_order = EXCLUDED.sort_order,
    public_description = EXCLUDED.public_description,
    feature_flags_json = EXCLUDED.feature_flags_json,
    updated_at = NOW();

UPDATE clients
SET
    billing_plan_code = COALESCE(NULLIF(TRIM(billing_plan_code), ''), 'free'),
    billing_status = COALESCE(NULLIF(TRIM(billing_status), ''), 'free'),
    billing_access_state = COALESCE(NULLIF(TRIM(billing_access_state), ''), 'free_active'),
    billing_updated_at = COALESCE(billing_updated_at, NOW());

INSERT INTO subscriptions (
    subscription_id,
    client_id,
    plan_code,
    status,
    cancel_at_period_end,
    created_at,
    updated_at
)
SELECT
    gen_random_uuid(),
    c.client_id,
    'free',
    'free',
    FALSE,
    NOW(),
    NOW()
FROM clients c
WHERE NOT EXISTS (
    SELECT 1 FROM subscriptions s WHERE s.client_id = c.client_id
);
