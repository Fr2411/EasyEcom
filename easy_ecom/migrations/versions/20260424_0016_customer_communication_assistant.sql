BEGIN;

CREATE TABLE IF NOT EXISTS assistant_playbooks (
    playbook_id UUID PRIMARY KEY,
    client_id UUID NOT NULL REFERENCES clients (client_id) ON DELETE CASCADE,
    status VARCHAR(32) NOT NULL DEFAULT 'active',
    business_type VARCHAR(64) NOT NULL DEFAULT 'general_retail',
    brand_personality VARCHAR(64) NOT NULL DEFAULT 'friendly',
    custom_instructions TEXT NOT NULL DEFAULT '',
    forbidden_claims TEXT NOT NULL DEFAULT '',
    sales_goals_json JSONB,
    policy_json JSONB,
    escalation_rules_json JSONB,
    industry_template_json JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_assistant_playbooks_client UNIQUE (client_id)
);

CREATE TABLE IF NOT EXISTS customer_channels (
    channel_id UUID PRIMARY KEY,
    client_id UUID NOT NULL REFERENCES clients (client_id) ON DELETE CASCADE,
    provider VARCHAR(32) NOT NULL,
    display_name VARCHAR(255) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'inactive',
    external_account_id VARCHAR(128) NOT NULL DEFAULT '',
    webhook_key VARCHAR(128) NOT NULL,
    default_location_id UUID,
    auto_send_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    config_json JSONB,
    last_inbound_at TIMESTAMPTZ,
    last_outbound_at TIMESTAMPTZ,
    created_by_user_id UUID REFERENCES users (user_id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_customer_channels_client_channel UNIQUE (client_id, channel_id),
    CONSTRAINT uq_customer_channels_client_provider_account UNIQUE (client_id, provider, external_account_id),
    CONSTRAINT uq_customer_channels_webhook_key UNIQUE (webhook_key),
    CONSTRAINT fk_customer_channels_client_default_location
        FOREIGN KEY (client_id, default_location_id)
        REFERENCES locations (client_id, location_id),
    CONSTRAINT fk_customer_channels_client_created_by_user
        FOREIGN KEY (client_id, created_by_user_id)
        REFERENCES users (client_id, user_id)
);

CREATE INDEX IF NOT EXISTS ix_customer_channels_client_id ON customer_channels (client_id);
CREATE INDEX IF NOT EXISTS ix_customer_channels_client_status ON customer_channels (client_id, status);
CREATE INDEX IF NOT EXISTS ix_customer_channels_provider ON customer_channels (provider);
CREATE INDEX IF NOT EXISTS ix_customer_channels_webhook_key ON customer_channels (webhook_key);

CREATE TABLE IF NOT EXISTS customer_conversations (
    conversation_id UUID PRIMARY KEY,
    client_id UUID NOT NULL REFERENCES clients (client_id) ON DELETE CASCADE,
    channel_id UUID NOT NULL,
    customer_id UUID,
    draft_order_id UUID,
    external_sender_id VARCHAR(160) NOT NULL,
    external_sender_name VARCHAR(255) NOT NULL DEFAULT '',
    external_sender_phone VARCHAR(64) NOT NULL DEFAULT '',
    external_sender_email VARCHAR(255) NOT NULL DEFAULT '',
    status VARCHAR(32) NOT NULL DEFAULT 'open',
    latest_intent VARCHAR(64) NOT NULL DEFAULT '',
    latest_summary TEXT NOT NULL DEFAULT '',
    memory_json JSONB,
    escalation_reason TEXT NOT NULL DEFAULT '',
    last_message_preview VARCHAR(280) NOT NULL DEFAULT '',
    last_message_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_customer_conversations_client_conversation UNIQUE (client_id, conversation_id),
    CONSTRAINT uq_customer_conversations_channel_sender UNIQUE (channel_id, external_sender_id),
    CONSTRAINT fk_customer_conversations_client_channel
        FOREIGN KEY (client_id, channel_id)
        REFERENCES customer_channels (client_id, channel_id)
        ON DELETE CASCADE,
    CONSTRAINT fk_customer_conversations_client_customer
        FOREIGN KEY (client_id, customer_id)
        REFERENCES customers (client_id, customer_id),
    CONSTRAINT fk_customer_conversations_client_draft_order
        FOREIGN KEY (client_id, draft_order_id)
        REFERENCES sales_orders (client_id, sales_order_id)
);

CREATE INDEX IF NOT EXISTS ix_customer_conversations_client_id ON customer_conversations (client_id);
CREATE INDEX IF NOT EXISTS ix_customer_conversations_client_status ON customer_conversations (client_id, status);
CREATE INDEX IF NOT EXISTS ix_customer_conversations_last_message ON customer_conversations (client_id, last_message_at);

CREATE TABLE IF NOT EXISTS customer_messages (
    message_id UUID PRIMARY KEY,
    client_id UUID NOT NULL REFERENCES clients (client_id) ON DELETE CASCADE,
    conversation_id UUID NOT NULL,
    channel_id UUID NOT NULL,
    direction VARCHAR(16) NOT NULL,
    sender_role VARCHAR(32) NOT NULL DEFAULT 'customer',
    provider_event_id VARCHAR(160) NOT NULL DEFAULT '',
    message_text TEXT NOT NULL DEFAULT '',
    content_summary VARCHAR(280) NOT NULL DEFAULT '',
    outbound_status VARCHAR(32) NOT NULL DEFAULT 'sent',
    raw_payload_json JSONB,
    metadata_json JSONB,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_customer_messages_client_message UNIQUE (client_id, message_id),
    CONSTRAINT fk_customer_messages_client_conversation
        FOREIGN KEY (client_id, conversation_id)
        REFERENCES customer_conversations (client_id, conversation_id)
        ON DELETE CASCADE,
    CONSTRAINT fk_customer_messages_client_channel
        FOREIGN KEY (client_id, channel_id)
        REFERENCES customer_channels (client_id, channel_id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS ix_customer_messages_client_id ON customer_messages (client_id);
CREATE INDEX IF NOT EXISTS ix_customer_messages_conversation ON customer_messages (client_id, conversation_id, occurred_at);
CREATE INDEX IF NOT EXISTS ix_customer_messages_channel ON customer_messages (client_id, channel_id, occurred_at);
CREATE INDEX IF NOT EXISTS ix_customer_messages_provider_event ON customer_messages (client_id, provider_event_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_customer_messages_client_provider_event
    ON customer_messages (client_id, provider_event_id)
    WHERE provider_event_id <> '';

CREATE TABLE IF NOT EXISTS assistant_runs (
    run_id UUID PRIMARY KEY,
    client_id UUID NOT NULL REFERENCES clients (client_id) ON DELETE CASCADE,
    conversation_id UUID NOT NULL,
    inbound_message_id UUID NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'running',
    model_provider VARCHAR(32) NOT NULL DEFAULT 'nvidia',
    model_name VARCHAR(128) NOT NULL DEFAULT '',
    prompt_snapshot_json JSONB,
    response_text TEXT NOT NULL DEFAULT '',
    validation_status VARCHAR(32) NOT NULL DEFAULT 'pending',
    escalation_required BOOLEAN NOT NULL DEFAULT FALSE,
    escalation_reason TEXT NOT NULL DEFAULT '',
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    total_tokens INTEGER,
    error_message TEXT NOT NULL DEFAULT '',
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_assistant_runs_client_run UNIQUE (client_id, run_id),
    CONSTRAINT fk_assistant_runs_client_conversation
        FOREIGN KEY (client_id, conversation_id)
        REFERENCES customer_conversations (client_id, conversation_id)
        ON DELETE CASCADE,
    CONSTRAINT fk_assistant_runs_client_inbound_message
        FOREIGN KEY (client_id, inbound_message_id)
        REFERENCES customer_messages (client_id, message_id)
);

CREATE INDEX IF NOT EXISTS ix_assistant_runs_client_id ON assistant_runs (client_id);
CREATE INDEX IF NOT EXISTS ix_assistant_runs_conversation ON assistant_runs (client_id, conversation_id, created_at);
CREATE INDEX IF NOT EXISTS ix_assistant_runs_status ON assistant_runs (client_id, status);

CREATE TABLE IF NOT EXISTS assistant_tool_calls (
    tool_call_id UUID PRIMARY KEY,
    client_id UUID NOT NULL REFERENCES clients (client_id) ON DELETE CASCADE,
    run_id UUID NOT NULL,
    conversation_id UUID NOT NULL,
    provider_tool_call_id VARCHAR(160) NOT NULL DEFAULT '',
    tool_name VARCHAR(128) NOT NULL,
    tool_arguments_json JSONB,
    tool_result_json JSONB,
    validation_status VARCHAR(32) NOT NULL DEFAULT 'ok',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_assistant_tool_calls_client_run
        FOREIGN KEY (client_id, run_id)
        REFERENCES assistant_runs (client_id, run_id)
        ON DELETE CASCADE,
    CONSTRAINT fk_assistant_tool_calls_client_conversation
        FOREIGN KEY (client_id, conversation_id)
        REFERENCES customer_conversations (client_id, conversation_id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS ix_assistant_tool_calls_client_id ON assistant_tool_calls (client_id);
CREATE INDEX IF NOT EXISTS ix_assistant_tool_calls_run ON assistant_tool_calls (client_id, run_id, created_at);

COMMIT;
