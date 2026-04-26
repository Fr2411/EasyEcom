BEGIN;

CREATE TABLE IF NOT EXISTS ai_agent_profiles (
    ai_agent_profile_id UUID PRIMARY KEY,
    client_id UUID NOT NULL REFERENCES clients (client_id) ON DELETE CASCADE,
    is_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    display_name VARCHAR(255) NOT NULL DEFAULT 'Website sales assistant',
    n8n_webhook_url TEXT NOT NULL DEFAULT '',
    persona_prompt TEXT NOT NULL DEFAULT '',
    store_policy TEXT NOT NULL DEFAULT '',
    faq_json JSONB,
    escalation_rules_json JSONB,
    allowed_actions_json JSONB,
    default_location_id UUID,
    opening_message TEXT NOT NULL DEFAULT '',
    handoff_message TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_ai_agent_profiles_client UNIQUE (client_id),
    CONSTRAINT uq_ai_agent_profiles_client_profile_id UNIQUE (client_id, ai_agent_profile_id),
    CONSTRAINT fk_ai_agent_profiles_default_location_tenant
        FOREIGN KEY (client_id, default_location_id)
        REFERENCES locations (client_id, location_id)
);

CREATE TABLE IF NOT EXISTS ai_chat_channels (
    ai_chat_channel_id UUID PRIMARY KEY,
    client_id UUID NOT NULL REFERENCES clients (client_id) ON DELETE CASCADE,
    agent_profile_id UUID NOT NULL,
    channel_type VARCHAR(32) NOT NULL DEFAULT 'website',
    display_name VARCHAR(255) NOT NULL DEFAULT 'Website chat',
    status VARCHAR(32) NOT NULL DEFAULT 'active',
    widget_key VARCHAR(96) NOT NULL,
    allowed_origins_json JSONB,
    default_location_id UUID,
    created_by_user_id UUID,
    last_inbound_at TIMESTAMPTZ,
    last_outbound_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_ai_chat_channels_widget_key UNIQUE (widget_key),
    CONSTRAINT uq_ai_chat_channels_client_type UNIQUE (client_id, channel_type),
    CONSTRAINT uq_ai_chat_channels_client_channel_id UNIQUE (client_id, ai_chat_channel_id),
    CONSTRAINT fk_ai_chat_channels_profile_tenant
        FOREIGN KEY (client_id, agent_profile_id)
        REFERENCES ai_agent_profiles (client_id, ai_agent_profile_id),
    CONSTRAINT fk_ai_chat_channels_default_location_tenant
        FOREIGN KEY (client_id, default_location_id)
        REFERENCES locations (client_id, location_id),
    CONSTRAINT fk_ai_chat_channels_created_by_tenant
        FOREIGN KEY (client_id, created_by_user_id)
        REFERENCES users (client_id, user_id)
);

CREATE INDEX IF NOT EXISTS ix_ai_chat_channels_client_id ON ai_chat_channels (client_id);
CREATE INDEX IF NOT EXISTS ix_ai_chat_channels_client_status ON ai_chat_channels (client_id, status);
CREATE INDEX IF NOT EXISTS ix_ai_chat_channels_widget_key ON ai_chat_channels (widget_key);

CREATE TABLE IF NOT EXISTS ai_conversations (
    ai_conversation_id UUID PRIMARY KEY,
    client_id UUID NOT NULL REFERENCES clients (client_id) ON DELETE CASCADE,
    ai_chat_channel_id UUID NOT NULL,
    customer_id UUID,
    browser_session_id VARCHAR(128) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'open',
    customer_name_snapshot VARCHAR(255) NOT NULL DEFAULT '',
    customer_phone_snapshot VARCHAR(64) NOT NULL DEFAULT '',
    customer_email_snapshot VARCHAR(255) NOT NULL DEFAULT '',
    customer_address_snapshot TEXT NOT NULL DEFAULT '',
    latest_intent VARCHAR(64) NOT NULL DEFAULT '',
    latest_summary TEXT NOT NULL DEFAULT '',
    handoff_reason TEXT NOT NULL DEFAULT '',
    last_message_preview VARCHAR(280) NOT NULL DEFAULT '',
    last_message_at TIMESTAMPTZ,
    metadata_json JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_ai_conversations_channel_session UNIQUE (ai_chat_channel_id, browser_session_id),
    CONSTRAINT uq_ai_conversations_client_conversation_id UNIQUE (client_id, ai_conversation_id),
    CONSTRAINT fk_ai_conversations_channel_tenant
        FOREIGN KEY (client_id, ai_chat_channel_id)
        REFERENCES ai_chat_channels (client_id, ai_chat_channel_id),
    CONSTRAINT fk_ai_conversations_customer_tenant
        FOREIGN KEY (client_id, customer_id)
        REFERENCES customers (client_id, customer_id)
);

CREATE INDEX IF NOT EXISTS ix_ai_conversations_client_status ON ai_conversations (client_id, status);
CREATE INDEX IF NOT EXISTS ix_ai_conversations_client_last_message ON ai_conversations (client_id, last_message_at);

CREATE TABLE IF NOT EXISTS ai_messages (
    ai_message_id UUID PRIMARY KEY,
    client_id UUID NOT NULL REFERENCES clients (client_id) ON DELETE CASCADE,
    ai_conversation_id UUID NOT NULL,
    ai_chat_channel_id UUID NOT NULL,
    direction VARCHAR(16) NOT NULL,
    message_text TEXT NOT NULL DEFAULT '',
    content_summary VARCHAR(280) NOT NULL DEFAULT '',
    raw_payload_json JSONB,
    ai_metadata_json JSONB,
    model_name VARCHAR(64) NOT NULL DEFAULT '',
    error_message TEXT NOT NULL DEFAULT '',
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_ai_messages_client_message_id UNIQUE (client_id, ai_message_id),
    CONSTRAINT fk_ai_messages_conversation_tenant
        FOREIGN KEY (client_id, ai_conversation_id)
        REFERENCES ai_conversations (client_id, ai_conversation_id),
    CONSTRAINT fk_ai_messages_channel_tenant
        FOREIGN KEY (client_id, ai_chat_channel_id)
        REFERENCES ai_chat_channels (client_id, ai_chat_channel_id)
);

CREATE INDEX IF NOT EXISTS ix_ai_messages_client_conversation ON ai_messages (client_id, ai_conversation_id, occurred_at);

CREATE TABLE IF NOT EXISTS ai_tool_calls (
    ai_tool_call_id UUID PRIMARY KEY,
    client_id UUID NOT NULL REFERENCES clients (client_id) ON DELETE CASCADE,
    ai_conversation_id UUID NOT NULL,
    ai_message_id UUID,
    tool_name VARCHAR(96) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'succeeded',
    request_json JSONB,
    response_json JSONB,
    error_message TEXT NOT NULL DEFAULT '',
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_ai_tool_calls_conversation_tenant
        FOREIGN KEY (client_id, ai_conversation_id)
        REFERENCES ai_conversations (client_id, ai_conversation_id),
    CONSTRAINT fk_ai_tool_calls_message_tenant
        FOREIGN KEY (client_id, ai_message_id)
        REFERENCES ai_messages (client_id, ai_message_id)
);

CREATE INDEX IF NOT EXISTS ix_ai_tool_calls_client_conversation ON ai_tool_calls (client_id, ai_conversation_id, created_at);

ALTER TABLE sales_orders
    ADD COLUMN IF NOT EXISTS source_channel_id UUID;

ALTER TABLE sales_orders
    ADD COLUMN IF NOT EXISTS source_conversation_id UUID;

CREATE INDEX IF NOT EXISTS ix_sales_orders_source_channel_id ON sales_orders (client_id, source_channel_id);
CREATE INDEX IF NOT EXISTS ix_sales_orders_source_conversation_id ON sales_orders (client_id, source_conversation_id);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_sales_orders_ai_source_channel_tenant'
    ) THEN
        ALTER TABLE sales_orders
            ADD CONSTRAINT fk_sales_orders_ai_source_channel_tenant
            FOREIGN KEY (client_id, source_channel_id)
            REFERENCES ai_chat_channels (client_id, ai_chat_channel_id);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_sales_orders_ai_source_conversation_tenant'
    ) THEN
        ALTER TABLE sales_orders
            ADD CONSTRAINT fk_sales_orders_ai_source_conversation_tenant
            FOREIGN KEY (client_id, source_conversation_id)
            REFERENCES ai_conversations (client_id, ai_conversation_id);
    END IF;
END $$;

COMMIT;
