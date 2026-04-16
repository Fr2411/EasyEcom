-- WARNING: destructive operation for controlled ops-only environments.
-- Drops all tables in schema public so migrations can rebuild from scratch.
BEGIN;

DO $$
DECLARE
    target RECORD;
BEGIN
    FOR target IN
        SELECT tablename
        FROM pg_tables
        WHERE schemaname = 'public'
    LOOP
        EXECUTE format('DROP TABLE IF EXISTS public.%I CASCADE', target.tablename);
    END LOOP;
END $$;

COMMIT;
