#!/usr/bin/env bash
set -euo pipefail

PORT="${PORT:-8080}"

python3 -m easy_ecom.scripts.init_data

exec python3 -m streamlit run easy_ecom/app/main.py \
  --server.address 0.0.0.0 \
  --server.port "${PORT}" \
  --server.headless true
