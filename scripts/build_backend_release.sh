#!/usr/bin/env bash
set -euo pipefail

DEPLOY_REF="${1:-HEAD}"
OUTPUT_PATH="${2:-}"

DEPLOY_SHA="$(git rev-parse --verify "${DEPLOY_REF}^{commit}")"

if [[ -z "${OUTPUT_PATH}" ]]; then
  OUTPUT_DIR="$(mktemp -d "/tmp/easyecom-backend-${DEPLOY_SHA:0:12}-XXXXXX")"
  OUTPUT_PATH="${OUTPUT_DIR}/backend-release.tar.gz"
fi

git archive --format=tar "${DEPLOY_SHA}" pyproject.toml startup.sh easy_ecom | gzip -n > "${OUTPUT_PATH}"

echo "${OUTPUT_PATH}"
