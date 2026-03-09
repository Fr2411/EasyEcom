#!/usr/bin/env bash
set -euo pipefail

PORT="${PORT:-8080}"

python3 -m easy_ecom.scripts.init_data

exec python3 -m uvicorn easy_ecom.api.main:app \
  --host 0.0.0.0 \
  --port "${PORT}"
