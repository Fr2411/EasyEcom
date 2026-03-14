#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "[dbeaver] Opening the SSH gateway to RDS through EC2."
echo "[dbeaver] Keep this terminal open while DBeaver is connected."
echo "[dbeaver] DBeaver connection settings:"
echo "  Host: 127.0.0.1"
echo "  Port: 5433"
echo "  Database: easyecom"
echo "  User: easyecom_admin"
echo "  Password: use the current POSTGRES_PASSWORD from the EC2 .env or your AWS secret"
echo "  SSL: require or preferred without strict hostname verification"

exec "${SCRIPT_DIR}/db_tunnel.sh"
