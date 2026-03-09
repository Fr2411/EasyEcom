#!/usr/bin/env bash
set -euo pipefail

echo "[db] Connecting to RDS via localhost:5433"
psql "host=127.0.0.1 port=5433 dbname=easyecom user=easyecom_admin sslmode=require"
