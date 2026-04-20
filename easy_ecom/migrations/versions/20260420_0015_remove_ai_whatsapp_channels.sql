BEGIN;

ALTER TABLE IF EXISTS sales_orders
    DROP COLUMN IF EXISTS source_agent_draft_id;

ALTER TABLE IF EXISTS sales_orders
    DROP COLUMN IF EXISTS source_conversation_id;

ALTER TABLE IF EXISTS sales_orders
    DROP COLUMN IF EXISTS source_channel_id;

DROP INDEX IF EXISTS ix_sales_orders_source_conversation_id;

DROP TABLE IF EXISTS channel_jobs CASCADE;
DROP TABLE IF EXISTS channel_message_product_mentions CASCADE;
DROP TABLE IF EXISTS ai_review_drafts CASCADE;
DROP TABLE IF EXISTS channel_messages CASCADE;
DROP TABLE IF EXISTS channel_conversations CASCADE;
DROP TABLE IF EXISTS tenant_agent_profiles CASCADE;
DROP TABLE IF EXISTS channel_integrations CASCADE;

COMMIT;
