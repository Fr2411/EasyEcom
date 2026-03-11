BEGIN;

CREATE TABLE IF NOT EXISTS ai_review_drafts (
  draft_id VARCHAR(64) PRIMARY KEY,
  client_id VARCHAR(64) NOT NULL,
  conversation_id VARCHAR(64) NOT NULL,
  inbound_message_id VARCHAR(64) NOT NULL,
  ai_draft_text TEXT NOT NULL DEFAULT '',
  edited_text TEXT NOT NULL DEFAULT '',
  final_text TEXT NOT NULL DEFAULT '',
  status VARCHAR(32) NOT NULL DEFAULT 'draft_created',
  intent VARCHAR(64) NOT NULL DEFAULT '',
  confidence VARCHAR(32) NOT NULL DEFAULT '',
  grounding_json TEXT NOT NULL DEFAULT '{}',
  requested_by_user_id VARCHAR(64) NOT NULL DEFAULT '',
  approved_by_user_id VARCHAR(64) NOT NULL DEFAULT '',
  sent_by_user_id VARCHAR(64) NOT NULL DEFAULT '',
  created_at VARCHAR(64) NOT NULL DEFAULT '',
  updated_at VARCHAR(64) NOT NULL DEFAULT '',
  approved_at VARCHAR(64) NOT NULL DEFAULT '',
  sent_at VARCHAR(64) NOT NULL DEFAULT '',
  failed_reason TEXT NOT NULL DEFAULT '',
  send_result_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_ai_review_drafts_client ON ai_review_drafts(client_id);
CREATE INDEX IF NOT EXISTS idx_ai_review_drafts_conversation ON ai_review_drafts(conversation_id);
CREATE INDEX IF NOT EXISTS idx_ai_review_drafts_inbound_message ON ai_review_drafts(inbound_message_id);
CREATE INDEX IF NOT EXISTS idx_ai_review_drafts_status ON ai_review_drafts(status);

COMMIT;
