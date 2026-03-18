BEGIN;

CREATE UNIQUE INDEX IF NOT EXISTS uq_channel_messages_client_provider_event
    ON channel_messages (client_id, provider_event_id)
    WHERE provider_event_id <> '';

COMMIT;
