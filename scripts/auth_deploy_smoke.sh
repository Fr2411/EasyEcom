#!/usr/bin/env bash
set -euo pipefail

API_BASE_URL="${API_BASE_URL:-${1:-}}"
SESSION_COOKIE="${SESSION_COOKIE:-}"
CLIENT_ID="${CLIENT_ID:-}"
CHANNEL_ID="${CHANNEL_ID:-}"
SMOKE_RECIPIENT="${SMOKE_RECIPIENT:-}"
SMOKE_TEXT="${SMOKE_TEXT:-EasyEcom smoke test. Reply path is working.}"

if [[ -z "${API_BASE_URL}" ]]; then
  echo "Usage: API_BASE_URL=https://api.example.com scripts/auth_deploy_smoke.sh"
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

run_post_check() {
  local label="$1"
  local path="$2"
  local body="${3:-{}}"
  local require_session="${4:-true}"
  local tmp_file
  local http_code
  tmp_file="$(mktemp)"

  if [[ "${require_session}" == "true" && -z "${SESSION_COOKIE}" ]]; then
    echo "[${label}] skipped: SESSION_COOKIE not provided"
    rm -f "${tmp_file}"
    return
  fi

  local curl_args=(
    -sS
    -o "${tmp_file}"
    -w '%{http_code}'
    -X POST
    -H "Content-Type: application/json"
    -d "${body}"
  )
  if [[ -n "${SESSION_COOKIE}" ]]; then
    curl_args+=(-H "Cookie: ${SESSION_COOKIE}")
  fi

  http_code="$(curl "${curl_args[@]}" "${api_url}${path}")"

  echo "[${label}] POST ${path} -> HTTP ${http_code}"
  cat "${tmp_file}"
  echo
  rm -f "${tmp_file}"

  if [[ "${http_code}" != "200" ]]; then
    echo "[${label}] failed: expected HTTP 200"
    exit 1
  fi
}

echo "[auth-smoke] API base: ${api_url}"
run_check "health" "/health" "false"
run_check "health-live" "/health/live" "false"
run_check "health-ready" "/health/ready" "false"
run_check "auth-me" "/auth/me" "true"
run_check "session-me" "/session/me" "true"

if [[ -n "${SESSION_COOKIE}" ]]; then
  integrations_path="/integrations/channels"
  if [[ -n "${CLIENT_ID}" ]]; then
    integrations_path="${integrations_path}?client_id=${CLIENT_ID}"
  fi
  run_check "integrations" "${integrations_path}" "true"
fi

if [[ -n "${CHANNEL_ID}" ]]; then
  run_post_check "channel-diagnostics" "/integrations/channels/${CHANNEL_ID}/run-diagnostics" "{}" "true"
fi

if [[ -n "${CHANNEL_ID}" && -n "${SMOKE_RECIPIENT}" ]]; then
  smoke_body="$(printf '{"recipient":"%s","text":"%s"}' "${SMOKE_RECIPIENT}" "${SMOKE_TEXT}")"
  run_post_check "channel-smoke" "/integrations/channels/${CHANNEL_ID}/send-smoke" "${smoke_body}" "true"
fi

echo "[auth-smoke] completed"
