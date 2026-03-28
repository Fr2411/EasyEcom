BEGIN;

CREATE TABLE IF NOT EXISTS finance_transactions (
    transaction_id UUID PRIMARY KEY,
    client_id UUID NOT NULL REFERENCES clients(client_id) ON DELETE CASCADE,
    origin_type VARCHAR(64) NOT NULL DEFAULT 'manual_payment',
    origin_id UUID NULL,
    direction VARCHAR(8) NOT NULL DEFAULT 'in',
    status VARCHAR(32) NOT NULL DEFAULT 'posted',
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    amount NUMERIC(12, 2) NOT NULL DEFAULT 0,
    currency_code VARCHAR(16) NOT NULL DEFAULT 'USD',
    reference VARCHAR(128) NOT NULL DEFAULT '',
    note TEXT NOT NULL DEFAULT '',
    counterparty_type VARCHAR(32) NULL,
    counterparty_id UUID NULL,
    counterparty_name VARCHAR(255) NOT NULL DEFAULT '',
    created_by_user_id UUID NULL REFERENCES users(user_id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_finance_transactions_client_id ON finance_transactions (client_id);
CREATE INDEX IF NOT EXISTS ix_finance_transactions_origin_type ON finance_transactions (origin_type);
CREATE INDEX IF NOT EXISTS ix_finance_transactions_origin_id ON finance_transactions (origin_id);
CREATE INDEX IF NOT EXISTS ix_finance_transactions_direction ON finance_transactions (direction);
CREATE INDEX IF NOT EXISTS ix_finance_transactions_status ON finance_transactions (status);
CREATE INDEX IF NOT EXISTS ix_finance_transactions_occurred_at ON finance_transactions (occurred_at);
CREATE INDEX IF NOT EXISTS ix_finance_transactions_counterparty_type ON finance_transactions (counterparty_type);

CREATE TABLE IF NOT EXISTS finance_transaction_links (
    finance_transaction_link_id UUID PRIMARY KEY,
    client_id UUID NOT NULL REFERENCES clients(client_id) ON DELETE CASCADE,
    transaction_id UUID NOT NULL REFERENCES finance_transactions(transaction_id) ON DELETE CASCADE,
    origin_type VARCHAR(64) NOT NULL,
    origin_id UUID NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_finance_transaction_links_origin_transaction
        UNIQUE (client_id, origin_type, origin_id, transaction_id)
);

CREATE INDEX IF NOT EXISTS ix_finance_transaction_links_client_id ON finance_transaction_links (client_id);
CREATE INDEX IF NOT EXISTS ix_finance_transaction_links_transaction_id ON finance_transaction_links (transaction_id);
CREATE INDEX IF NOT EXISTS ix_finance_transaction_links_origin_type ON finance_transaction_links (origin_type);
CREATE INDEX IF NOT EXISTS ix_finance_transaction_links_origin_id ON finance_transaction_links (origin_id);

COMMIT;
