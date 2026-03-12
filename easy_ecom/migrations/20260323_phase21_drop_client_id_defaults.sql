-- Prevent implicit tenant assignment on client_id writes.
-- This migration is idempotent and safe on production PostgreSQL.
ALTER TABLE users ALTER COLUMN client_id DROP DEFAULT;
ALTER TABLE clients ALTER COLUMN client_id DROP DEFAULT;
