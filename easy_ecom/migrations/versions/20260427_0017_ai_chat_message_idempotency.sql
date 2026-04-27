BEGIN;

ALTER TABLE ai_messages
    ADD COLUMN IF NOT EXISTS client_message_id VARCHAR(128);

ALTER TABLE ai_messages
    ADD COLUMN IF NOT EXISTS responded_to_ai_message_id UUID;

CREATE UNIQUE INDEX IF NOT EXISTS uq_ai_messages_client_conversation_client_message_id
    ON ai_messages (client_id, ai_conversation_id, client_message_id)
    WHERE client_message_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS ix_ai_messages_client_response_link
    ON ai_messages (client_id, responded_to_ai_message_id);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_ai_messages_responded_to_tenant'
    ) THEN
        ALTER TABLE ai_messages
            ADD CONSTRAINT fk_ai_messages_responded_to_tenant
            FOREIGN KEY (client_id, responded_to_ai_message_id)
            REFERENCES ai_messages (client_id, ai_message_id);
    END IF;
END $$;

COMMIT;
