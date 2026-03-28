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
  OUTPUT_DIR="$(mktemp -d "/tmp/easyecom-backend-${DEPLOY_SHA:0:12}-XXXXXX")"
  OUTPUT_PATH="${OUTPUT_DIR}/backend-release.tar.gz"
fi

{
  printf '%s\n' "pyproject.toml" "startup.sh"
  find easy_ecom -type f \
    ! -path '*/__pycache__/*' \
    ! -name '*.pyc' \
    ! -name '*.pyo' \
    ! -name '._*' \
    ! -name '*.bak' \
    ! -name '*.backup' \
    ! -name '*.backup2' \
    ! -name '*.orig' \
    ! -name '*.work' \
    ! -name '*.debug'
} | LC_ALL=C sort > "${FILE_LIST}"

COPYFILE_DISABLE=1 tar -czf "${OUTPUT_PATH}" -T "${FILE_LIST}"

echo "${OUTPUT_PATH}"
