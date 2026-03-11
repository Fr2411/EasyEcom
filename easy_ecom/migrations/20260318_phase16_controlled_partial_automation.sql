-- Phase 16: controlled partial automation

CREATE TABLE IF NOT EXISTS tenant_automation_policies (
  policy_id VARCHAR(64) PRIMARY KEY,
  client_id VARCHAR(64) NOT NULL UNIQUE,
  automation_enabled VARCHAR(8) NOT NULL DEFAULT 'false',
  auto_send_enabled VARCHAR(8) NOT NULL DEFAULT 'false',
  emergency_disabled VARCHAR(8) NOT NULL DEFAULT 'false',
  categories_json TEXT NOT NULL DEFAULT '{}',
  updated_by_user_id VARCHAR(64) NOT NULL DEFAULT '',
  created_at VARCHAR(64) NOT NULL,
  updated_at VARCHAR(64) NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_tenant_automation_policies_client ON tenant_automation_policies(client_id);

CREATE TABLE IF NOT EXISTS automation_decisions (
  decision_id VARCHAR(64) PRIMARY KEY,
  client_id VARCHAR(64) NOT NULL,
  conversation_id VARCHAR(64) NOT NULL,
  inbound_message_id VARCHAR(64) NOT NULL,
  policy_id VARCHAR(64) NOT NULL,
  category VARCHAR(64) NOT NULL DEFAULT '',
  classification_rule VARCHAR(120) NOT NULL DEFAULT '',
  recommended_action VARCHAR(64) NOT NULL DEFAULT 'human_review',
  outcome VARCHAR(64) NOT NULL DEFAULT 'escalated',
  reason TEXT NOT NULL DEFAULT '',
  confidence VARCHAR(32) NOT NULL DEFAULT '',
  candidate_reply TEXT NOT NULL DEFAULT '',
  audit_context_json TEXT NOT NULL DEFAULT '{}',
  run_by_user_id VARCHAR(64) NOT NULL DEFAULT '',
  created_at VARCHAR(64) NOT NULL,
  updated_at VARCHAR(64) NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_automation_decisions_client ON automation_decisions(client_id);
CREATE INDEX IF NOT EXISTS idx_automation_decisions_conversation ON automation_decisions(conversation_id);
CREATE INDEX IF NOT EXISTS idx_automation_decisions_outcome ON automation_decisions(outcome);

-- rollback
-- DROP TABLE IF EXISTS automation_decisions;
-- DROP TABLE IF EXISTS tenant_automation_policies;
