#!/usr/bin/env bash
set -euo pipefail

DEPLOY_REF="${1:-HEAD}"
OUTPUT_PATH="${2:-}"

DEPLOY_SHA="$(git rev-parse --verify "${DEPLOY_REF}^{commit}")"
FILE_LIST="$(mktemp /tmp/easyecom-backend-files-XXXXXX)"

cleanup() {
  rm -f "${FILE_LIST}"
}
trap cleanup EXIT

if [[ -z "${OUTPUT_PATH}" ]]; then
  OUTPUT_PATH="$(mktemp "/tmp/easyecom-backend-${DEPLOY_SHA:0:12}-XXXXXX.tar.gz")"
fi

git ls-tree -r --name-only "${DEPLOY_SHA}" -- pyproject.toml startup.sh easy_ecom \
  | grep -Ev '(^|/).*\.(bak|backup|backup2|orig|work|debug)$' > "${FILE_LIST}"

tar -czf "${OUTPUT_PATH}" -T "${FILE_LIST}"

echo "${OUTPUT_PATH}"
