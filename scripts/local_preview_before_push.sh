#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORT="${PREVIEW_PORT:-4173}"
RUN_GATE=1

if [[ "${1:-}" == "--skip-gate" ]]; then
  RUN_GATE=0
fi

cd "$ROOT_DIR"

if [[ "$RUN_GATE" -eq 1 ]]; then
  echo "[preview] Verifying backend importability"
  python3 -m compileall -q easy_ecom
fi

echo "[preview] Building frontend"
cd frontend
npm run typecheck
npm run build

echo "[preview] Starting internal preview on http://127.0.0.1:${PORT}"
echo "[preview] Press Ctrl+C to stop"
npm run start -- --hostname 127.0.0.1 --port "${PORT}"
