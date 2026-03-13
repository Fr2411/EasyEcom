#!/usr/bin/env bash
set -euo pipefail

STAMP="$(date +"%Y%m%d-%H%M%S")"
BACKUP_DIR="${1:-backups/rds-pre-reset-${STAMP}}"

mkdir -p "$BACKUP_DIR"

if [[ -n "${DATABASE_URL:-}" ]]; then
  CONNECTION="$DATABASE_URL"
else
  HOST="${PGHOST:-${POSTGRES_HOST:-127.0.0.1}}"
  PORT="${PGPORT:-${POSTGRES_PORT:-5433}}"
  DBNAME="${PGDATABASE:-${POSTGRES_DB:-easyecom}}"
  USER="${PGUSER:-${POSTGRES_USER:-easyecom_admin}}"
  PASSWORD="${PGPASSWORD:-${POSTGRES_PASSWORD:-}}"
  if [[ -n "$PASSWORD" ]]; then
    export PGPASSWORD="$PASSWORD"
  fi
  CONNECTION="host=${HOST} port=${PORT} dbname=${DBNAME} user=${USER} sslmode=require"
fi

echo "[backup] Writing logical export to ${BACKUP_DIR}"
if pg_dump --format=custom --file "${BACKUP_DIR}/easy_ecom_pre_reset.dump" "$CONNECTION"; then
  pg_dump --format=plain --schema-only --file "${BACKUP_DIR}/easy_ecom_pre_reset_schema.sql" "$CONNECTION"
  echo "[backup] Export complete via pg_dump"
  exit 0
fi

echo "[backup] pg_dump could not complete, falling back to schema manifest + table CSV export"
mkdir -p "${BACKUP_DIR}/tables"

psql "$CONNECTION" -v ON_ERROR_STOP=1 -c "\copy (
  SELECT table_name, column_name, data_type, is_nullable, column_default
  FROM information_schema.columns
  WHERE table_schema = 'public'
  ORDER BY table_name, ordinal_position
) TO '${BACKUP_DIR}/schema_manifest.csv' CSV HEADER"

TABLE_LIST_FILE="${BACKUP_DIR}/table_names.txt"
psql "$CONNECTION" -v ON_ERROR_STOP=1 -At -c "
  SELECT tablename
  FROM pg_tables
  WHERE schemaname = 'public'
  ORDER BY tablename
" > "$TABLE_LIST_FILE"

while IFS= read -r table_name; do
  [[ -z "$table_name" ]] && continue
  psql "$CONNECTION" -v ON_ERROR_STOP=1 -c "\\copy public.${table_name} TO '${BACKUP_DIR}/tables/${table_name}.csv' CSV HEADER"
done < "$TABLE_LIST_FILE"

echo "[backup] Export complete via table CSV fallback"
