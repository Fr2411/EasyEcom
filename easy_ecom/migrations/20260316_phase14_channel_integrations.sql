-- Phase 14: external channel integration foundation

CREATE TABLE IF NOT EXISTS channel_integrations (
  channel_id VARCHAR(64) PRIMARY KEY,
  client_id VARCHAR(64) NOT NULL,
  provider VARCHAR(32) NOT NULL,
  display_name VARCHAR(255) NOT NULL DEFAULT '',
  status VARCHAR(32) NOT NULL DEFAULT 'inactive',
  external_account_id VARCHAR(255) NOT NULL DEFAULT '',
  verify_token VARCHAR(255) NOT NULL DEFAULT '',
  inbound_secret VARCHAR(255) NOT NULL DEFAULT '',
  config_json TEXT NOT NULL DEFAULT '{}',
  created_at VARCHAR(64) NOT NULL DEFAULT '',
  updated_at VARCHAR(64) NOT NULL DEFAULT '',
  created_by_user_id VARCHAR(64) NOT NULL DEFAULT '',
  last_inbound_at VARCHAR(64) NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_channel_integrations_client_id ON channel_integrations (client_id);
CREATE INDEX IF NOT EXISTS idx_channel_integrations_provider ON channel_integrations (provider);
CREATE INDEX IF NOT EXISTS idx_channel_integrations_status ON channel_integrations (status);

CREATE TABLE IF NOT EXISTS channel_conversations (
  conversation_id VARCHAR(64) PRIMARY KEY,
  client_id VARCHAR(64) NOT NULL,
  channel_id VARCHAR(64) NOT NULL,
  external_sender_id VARCHAR(255) NOT NULL DEFAULT '',
  status VARCHAR(32) NOT NULL DEFAULT 'open',
  customer_id VARCHAR(64) NOT NULL DEFAULT '',
  linked_sale_id VARCHAR(64) NOT NULL DEFAULT '',
  created_at VARCHAR(64) NOT NULL DEFAULT '',
  updated_at VARCHAR(64) NOT NULL DEFAULT '',
  last_message_at VARCHAR(64) NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_channel_conversations_client_id ON channel_conversations (client_id);
CREATE INDEX IF NOT EXISTS idx_channel_conversations_channel_id ON channel_conversations (channel_id);
CREATE INDEX IF NOT EXISTS idx_channel_conversations_sender ON channel_conversations (external_sender_id);

CREATE TABLE IF NOT EXISTS channel_messages (
  message_id VARCHAR(64) PRIMARY KEY,
  client_id VARCHAR(64) NOT NULL,
  channel_id VARCHAR(64) NOT NULL,
  conversation_id VARCHAR(64) NOT NULL,
  direction VARCHAR(16) NOT NULL DEFAULT 'inbound',
  provider_event_id VARCHAR(255) NOT NULL DEFAULT '',
  external_sender_id VARCHAR(255) NOT NULL DEFAULT '',
  message_text TEXT NOT NULL DEFAULT '',
  content_summary VARCHAR(280) NOT NULL DEFAULT '',
  payload_json TEXT NOT NULL DEFAULT '{}',
  occurred_at VARCHAR(64) NOT NULL DEFAULT '',
  created_at VARCHAR(64) NOT NULL DEFAULT '',
  outbound_status VARCHAR(32) NOT NULL DEFAULT 'prepared',
  created_by_user_id VARCHAR(64) NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_channel_messages_client_id ON channel_messages (client_id);
CREATE INDEX IF NOT EXISTS idx_channel_messages_conversation_id ON channel_messages (conversation_id);
CREATE INDEX IF NOT EXISTS idx_channel_messages_direction ON channel_messages (direction);
CREATE INDEX IF NOT EXISTS idx_channel_messages_occurred_at ON channel_messages (occurred_at);

-- rollback:
-- DROP TABLE IF EXISTS channel_messages;
-- DROP TABLE IF EXISTS channel_conversations;
-- DROP TABLE IF EXISTS channel_integrations;
