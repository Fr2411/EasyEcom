#!/usr/bin/env bash
set -euo pipefail

echo "[db] Opening SSH tunnel to RDS..."
echo "[db] Keep this terminal open while using DBeaver."

ssh -N \
  -o IPQoS=throughput \
  -o IdentitiesOnly=yes \
  -i "$HOME/Downloads/EasyEcomKey.pem" \
  -L 127.0.0.1:5433:easyecom-db.cqv22y4iozfw.us-east-1.rds.amazonaws.com:5432 \
  ec2-user@44.197.250.127
