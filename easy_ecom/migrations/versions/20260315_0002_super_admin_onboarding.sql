BEGIN;

ALTER TABLE clients
ADD COLUMN IF NOT EXISTS contact_name VARCHAR(255) NOT NULL DEFAULT '';

UPDATE clients
SET contact_name = owner_name
WHERE coalesce(contact_name, '') = '';

ALTER TABLE users
ADD COLUMN IF NOT EXISTS user_code VARCHAR(160);

INSERT INTO roles (role_code, role_name, description)
VALUES
    ('CLIENT_STAFF', 'Client Staff', 'Operations access across core workflows'),
    ('FINANCE_STAFF', 'Finance Staff', 'Finance and reporting access')
ON CONFLICT (role_code) DO UPDATE
SET
    role_name = EXCLUDED.role_name,
    description = EXCLUDED.description;

UPDATE user_roles
SET role_code = 'CLIENT_STAFF'
WHERE role_code IN ('CLIENT_MANAGER', 'CLIENT_EMPLOYEE');

DELETE FROM user_roles newer
USING user_roles older
WHERE newer.ctid < older.ctid
  AND newer.user_id = older.user_id
  AND newer.role_code = older.role_code;

UPDATE user_roles
SET role_code = 'FINANCE_STAFF'
WHERE role_code = 'FINANCE_ONLY';

UPDATE user_invitations
SET role_code = 'CLIENT_STAFF'
WHERE role_code IN ('CLIENT_MANAGER', 'CLIENT_EMPLOYEE');

UPDATE user_invitations
SET role_code = 'FINANCE_STAFF'
WHERE role_code = 'FINANCE_ONLY';

DELETE FROM roles
WHERE role_code IN ('CLIENT_MANAGER', 'CLIENT_EMPLOYEE', 'FINANCE_ONLY');

WITH user_bases AS (
    SELECT
        u.user_id,
        regexp_replace(
            lower(
                trim(
                    both '-'
                    FROM regexp_replace(
                        coalesce(c.slug, 'client') || '-' ||
                        CASE
                            WHEN ur.role_code = 'SUPER_ADMIN' THEN 'super-admin'
                            WHEN ur.role_code = 'CLIENT_OWNER' THEN 'client-owner'
                            WHEN ur.role_code = 'CLIENT_STAFF' THEN 'client-staff'
                            WHEN ur.role_code = 'FINANCE_STAFF' THEN 'finance-staff'
                            ELSE lower(replace(coalesce(ur.role_code, 'user'), '_', '-'))
                        END || '-' ||
                        coalesce(u.name, 'user'),
                        '[^A-Za-z0-9]+',
                        '-',
                        'g'
                    )
                )
            ),
            '-+',
            '-',
            'g'
        ) AS base_code
    FROM users u
    JOIN clients c ON c.client_id = u.client_id
    LEFT JOIN LATERAL (
        SELECT role_code
        FROM user_roles
        WHERE user_id = u.user_id
        ORDER BY role_code
        LIMIT 1
    ) ur ON TRUE
),
ranked_codes AS (
    SELECT
        user_id,
        CASE
            WHEN row_number() OVER (PARTITION BY base_code ORDER BY user_id) = 1 THEN left(base_code, 160)
            ELSE left(base_code, 160 - length('-' || row_number() OVER (PARTITION BY base_code ORDER BY user_id)::text))
                || '-' || row_number() OVER (PARTITION BY base_code ORDER BY user_id)::text
        END AS generated_code
    FROM user_bases
)
UPDATE users u
SET user_code = ranked_codes.generated_code
FROM ranked_codes
WHERE ranked_codes.user_id = u.user_id
  AND (u.user_code IS NULL OR u.user_code = '');

ALTER TABLE users
ALTER COLUMN user_code SET NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'uq_users_user_code'
    ) THEN
        ALTER TABLE users ADD CONSTRAINT uq_users_user_code UNIQUE (user_code);
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS ix_users_user_code ON users (user_code);

COMMIT;
