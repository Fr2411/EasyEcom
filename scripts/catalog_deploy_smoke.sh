#!/usr/bin/env bash
set -euo pipefail

API_BASE_URL="${API_BASE_URL:-${1:-}}"
SESSION_COOKIE="${SESSION_COOKIE:-}"

if [[ -z "${API_BASE_URL}" ]]; then
  echo "Usage: API_BASE_URL=https://api.example.com scripts/catalog_deploy_smoke.sh"
  echo "Optional: SESSION_COOKIE='session=...'"
  exit 1
fi

api_url="${API_BASE_URL%/}"

run_check() {
  local label="$1"
  local path="$2"
  local expect_auth="${3:-false}"
  local tmp_file
  local http_code
  tmp_file="$(mktemp)"

  if [[ -n "${SESSION_COOKIE}" ]]; then
    http_code="$(curl -sS -o "${tmp_file}" -w '%{http_code}' -H "Cookie: ${SESSION_COOKIE}" "${api_url}${path}")"
  else
    http_code="$(curl -sS -o "${tmp_file}" -w '%{http_code}' "${api_url}${path}")"
  fi

  echo "[${label}] ${path} -> HTTP ${http_code}"
  cat "${tmp_file}"
  echo
  rm -f "${tmp_file}"

  if [[ "${expect_auth}" == "false" && "${http_code}" != "200" ]]; then
    echo "[${label}] failed: expected HTTP 200"
    exit 1
  fi

  if [[ "${expect_auth}" == "true" ]]; then
    if [[ -n "${SESSION_COOKIE}" && "${http_code}" != "200" ]]; then
      echo "[${label}] failed: expected HTTP 200 with SESSION_COOKIE provided"
      exit 1
    fi
    if [[ -z "${SESSION_COOKIE}" && "${http_code}" != "401" && "${http_code}" != "403" && "${http_code}" != "200" ]]; then
      echo "[${label}] unexpected status without SESSION_COOKIE"
      exit 1
    fi
  fi
}

echo "[catalog-smoke] API base: ${api_url}"
run_check "health" "/health" "false"
run_check "auth-me" "/auth/me" "true"
run_check "catalog-products" "/catalog/products" "true"

echo "[catalog-smoke] completed"
