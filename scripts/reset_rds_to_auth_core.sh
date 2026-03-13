#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SQL_FILE="${ROOT_DIR}/easy_ecom/migrations/20260314_auth_only_foundation.sql"

if [[ ! -f "$SQL_FILE" ]]; then
  echo "[reset] Missing SQL file: $SQL_FILE" >&2
  exit 1
fi

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

echo "[reset] Applying auth-only foundation reset"
psql "$CONNECTION" -v ON_ERROR_STOP=1 -f "$SQL_FILE"

echo "[reset] Re-seeding auth core"
python3 -m easy_ecom.scripts.init_data

echo "[reset] Auth-only foundation applied"
