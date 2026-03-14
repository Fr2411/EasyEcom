BEGIN;

CREATE TABLE IF NOT EXISTS user_page_access_overrides (
    override_id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    page_code VARCHAR(64) NOT NULL,
    is_allowed BOOLEAN NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_user_page_access_overrides_user_page UNIQUE (user_id, page_code)
);

CREATE INDEX IF NOT EXISTS ix_user_page_access_overrides_user_id
ON user_page_access_overrides (user_id);

COMMIT;
