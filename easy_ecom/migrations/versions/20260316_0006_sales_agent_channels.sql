BEGIN;

CREATE TABLE IF NOT EXISTS channel_integrations (
    channel_id UUID PRIMARY KEY,
    client_id UUID NOT NULL REFERENCES clients (client_id) ON DELETE CASCADE,
    provider VARCHAR(32) NOT NULL,
    display_name VARCHAR(255) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'inactive',
    external_account_id VARCHAR(128) NOT NULL DEFAULT '',
    phone_number_id VARCHAR(128) NOT NULL DEFAULT '',
    phone_number VARCHAR(64) NOT NULL DEFAULT '',
    webhook_key VARCHAR(128) NOT NULL UNIQUE,
    verify_token_hash VARCHAR(128) NOT NULL DEFAULT '',
    access_token TEXT NOT NULL DEFAULT '',
    app_secret TEXT NOT NULL DEFAULT '',
    default_location_id UUID REFERENCES locations (location_id) ON DELETE SET NULL,
    auto_send_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    config_json JSONB,
    last_inbound_at TIMESTAMPTZ,
    last_outbound_at TIMESTAMPTZ,
    created_by_user_id UUID REFERENCES users (user_id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_channel_integrations_client_provider_account UNIQUE (client_id, provider, external_account_id)
);

CREATE INDEX IF NOT EXISTS ix_channel_integrations_client_id ON channel_integrations (client_id);
CREATE INDEX IF NOT EXISTS ix_channel_integrations_provider ON channel_integrations (provider);
CREATE INDEX IF NOT EXISTS ix_channel_integrations_client_status ON channel_integrations (client_id, status);

CREATE TABLE IF NOT EXISTS tenant_agent_profiles (
    agent_profile_id UUID PRIMARY KEY,
    client_id UUID NOT NULL REFERENCES clients (client_id) ON DELETE CASCADE,
    channel_id UUID REFERENCES channel_integrations (channel_id) ON DELETE SET NULL,
    default_location_id UUID REFERENCES locations (location_id) ON DELETE SET NULL,
    is_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    auto_send_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    model_name VARCHAR(64) NOT NULL DEFAULT 'gpt-5',
    persona_prompt TEXT NOT NULL DEFAULT '',
    behavior_policy_json JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_tenant_agent_profiles_client UNIQUE (client_id)
);

CREATE INDEX IF NOT EXISTS ix_tenant_agent_profiles_client_id ON tenant_agent_profiles (client_id);

CREATE TABLE IF NOT EXISTS channel_conversations (
    conversation_id UUID PRIMARY KEY,
    client_id UUID NOT NULL REFERENCES clients (client_id) ON DELETE CASCADE,
    channel_id UUID NOT NULL REFERENCES channel_integrations (channel_id) ON DELETE CASCADE,
    customer_id UUID REFERENCES customers (customer_id) ON DELETE SET NULL,
    external_sender_id VARCHAR(128) NOT NULL,
    external_sender_phone VARCHAR(64) NOT NULL DEFAULT '',
    customer_name_snapshot VARCHAR(255) NOT NULL DEFAULT '',
    customer_phone_snapshot VARCHAR(64) NOT NULL DEFAULT '',
    customer_email_snapshot VARCHAR(255) NOT NULL DEFAULT '',
    status VARCHAR(32) NOT NULL DEFAULT 'open',
    customer_type_snapshot VARCHAR(32) NOT NULL DEFAULT 'new',
    behavior_tags_json JSONB,
    behavior_confidence NUMERIC(5, 2),
    lifetime_spend_snapshot NUMERIC(12, 2) NOT NULL DEFAULT 0,
    lifetime_order_count_snapshot INTEGER NOT NULL DEFAULT 0,
    last_order_at_snapshot TIMESTAMPTZ,
    latest_intent VARCHAR(64) NOT NULL DEFAULT '',
    latest_summary TEXT NOT NULL DEFAULT '',
    last_recommended_products_summary TEXT NOT NULL DEFAULT '',
    last_message_preview VARCHAR(280) NOT NULL DEFAULT '',
    linked_draft_order_id UUID REFERENCES sales_orders (sales_order_id) ON DELETE SET NULL,
    linked_draft_order_status VARCHAR(32) NOT NULL DEFAULT '',
    last_message_at TIMESTAMPTZ,
    handoff_requested_at TIMESTAMPTZ,
    metadata_json JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_channel_conversations_sender UNIQUE (channel_id, external_sender_id)
);

CREATE INDEX IF NOT EXISTS ix_channel_conversations_client_id ON channel_conversations (client_id);
CREATE INDEX IF NOT EXISTS ix_channel_conversations_last_message ON channel_conversations (client_id, last_message_at);
CREATE INDEX IF NOT EXISTS ix_channel_conversations_client_status ON channel_conversations (client_id, status);

CREATE TABLE IF NOT EXISTS channel_messages (
    message_id UUID PRIMARY KEY,
    client_id UUID NOT NULL REFERENCES clients (client_id) ON DELETE CASCADE,
    conversation_id UUID NOT NULL REFERENCES channel_conversations (conversation_id) ON DELETE CASCADE,
    channel_id UUID NOT NULL REFERENCES channel_integrations (channel_id) ON DELETE CASCADE,
    direction VARCHAR(16) NOT NULL,
    external_sender_id VARCHAR(128) NOT NULL DEFAULT '',
    provider_event_id VARCHAR(128) NOT NULL DEFAULT '',
    provider_status VARCHAR(64) NOT NULL DEFAULT '',
    message_text TEXT NOT NULL DEFAULT '',
    content_summary VARCHAR(280) NOT NULL DEFAULT '',
    raw_payload_json JSONB,
    ai_metadata_json JSONB,
    structured_extraction_json JSONB,
    model_name VARCHAR(64) NOT NULL DEFAULT '',
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    total_tokens INTEGER,
    error_message TEXT NOT NULL DEFAULT '',
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    outbound_status VARCHAR(32) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_channel_messages_client_id ON channel_messages (client_id);
CREATE INDEX IF NOT EXISTS ix_channel_messages_conversation ON channel_messages (client_id, conversation_id, occurred_at);
CREATE INDEX IF NOT EXISTS ix_channel_messages_provider_event ON channel_messages (client_id, provider_event_id);

CREATE TABLE IF NOT EXISTS ai_review_drafts (
    draft_id UUID PRIMARY KEY,
    client_id UUID NOT NULL REFERENCES clients (client_id) ON DELETE CASCADE,
    conversation_id UUID NOT NULL REFERENCES channel_conversations (conversation_id) ON DELETE CASCADE,
    inbound_message_id UUID NOT NULL REFERENCES channel_messages (message_id) ON DELETE CASCADE,
    linked_sales_order_id UUID REFERENCES sales_orders (sales_order_id) ON DELETE SET NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'new',
    ai_draft_text TEXT NOT NULL DEFAULT '',
    edited_text TEXT NOT NULL DEFAULT '',
    final_text TEXT NOT NULL DEFAULT '',
    intent VARCHAR(64) NOT NULL DEFAULT '',
    confidence NUMERIC(5, 2),
    grounding_json JSONB,
    reason_codes_json JSONB,
    requested_by_user_id UUID REFERENCES users (user_id) ON DELETE SET NULL,
    approved_by_user_id UUID REFERENCES users (user_id) ON DELETE SET NULL,
    sent_by_user_id UUID REFERENCES users (user_id) ON DELETE SET NULL,
    approved_at TIMESTAMPTZ,
    sent_at TIMESTAMPTZ,
    failed_reason TEXT,
    send_result_json JSONB,
    human_modified BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_ai_review_drafts_client_id ON ai_review_drafts (client_id);
CREATE INDEX IF NOT EXISTS ix_ai_review_drafts_status ON ai_review_drafts (client_id, status);

CREATE TABLE IF NOT EXISTS channel_message_product_mentions (
    mention_id UUID PRIMARY KEY,
    client_id UUID NOT NULL REFERENCES clients (client_id) ON DELETE CASCADE,
    message_id UUID NOT NULL REFERENCES channel_messages (message_id) ON DELETE CASCADE,
    conversation_id UUID NOT NULL REFERENCES channel_conversations (conversation_id) ON DELETE CASCADE,
    product_id UUID REFERENCES products (product_id) ON DELETE SET NULL,
    variant_id UUID REFERENCES product_variants (variant_id) ON DELETE SET NULL,
    mention_role VARCHAR(32) NOT NULL DEFAULT 'mentioned',
    quantity NUMERIC(14, 3),
    unit_price_amount NUMERIC(12, 2),
    min_price_amount NUMERIC(12, 2),
    available_to_sell_snapshot NUMERIC(14, 3),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_channel_message_product_mentions_client_id ON channel_message_product_mentions (client_id);
CREATE INDEX IF NOT EXISTS ix_channel_mentions_message ON channel_message_product_mentions (client_id, message_id);
CREATE INDEX IF NOT EXISTS ix_channel_mentions_conversation ON channel_message_product_mentions (client_id, conversation_id);

CREATE TABLE IF NOT EXISTS channel_jobs (
    job_id UUID PRIMARY KEY,
    client_id UUID NOT NULL REFERENCES clients (client_id) ON DELETE CASCADE,
    channel_id UUID NOT NULL REFERENCES channel_integrations (channel_id) ON DELETE CASCADE,
    conversation_id UUID REFERENCES channel_conversations (conversation_id) ON DELETE SET NULL,
    message_id UUID REFERENCES channel_messages (message_id) ON DELETE SET NULL,
    job_type VARCHAR(64) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'pending',
    attempts INTEGER NOT NULL DEFAULT 0,
    scheduled_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    payload_json JSONB,
    last_error TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_channel_jobs_client_id ON channel_jobs (client_id);
CREATE INDEX IF NOT EXISTS ix_channel_jobs_client_status ON channel_jobs (client_id, status, scheduled_at);

ALTER TABLE sales_orders
    ADD COLUMN IF NOT EXISTS source_type VARCHAR(32) NOT NULL DEFAULT 'manual';

ALTER TABLE sales_orders
    ADD COLUMN IF NOT EXISTS source_channel_id UUID REFERENCES channel_integrations (channel_id) ON DELETE SET NULL;

ALTER TABLE sales_orders
    ADD COLUMN IF NOT EXISTS source_conversation_id UUID REFERENCES channel_conversations (conversation_id) ON DELETE SET NULL;

ALTER TABLE sales_orders
    ADD COLUMN IF NOT EXISTS source_agent_draft_id UUID REFERENCES ai_review_drafts (draft_id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS ix_sales_orders_source_type ON sales_orders (source_type);
CREATE INDEX IF NOT EXISTS ix_sales_orders_source_conversation_id ON sales_orders (source_conversation_id);

COMMIT;
