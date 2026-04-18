#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$ROOT_DIR"

echo "[staging-gate] Checking repository surface"
./scripts/check_repo_surface.sh

echo "[staging-gate] Verifying backend importability"
python3 -m compileall -q easy_ecom

echo "[staging-gate] Running frontend quality checks"
cd frontend
npm run typecheck
npm run build

echo "[staging-gate] All checks passed"
