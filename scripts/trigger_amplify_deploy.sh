#!/usr/bin/env bash
set -euo pipefail

APP_ID="${AMPLIFY_APP_ID:-}"
BRANCH="${AMPLIFY_BRANCH:-main}"

if [[ -z "${APP_ID}" ]]; then
  echo "Usage: AMPLIFY_APP_ID=<app-id> [AMPLIFY_BRANCH=main] ./scripts/trigger_amplify_deploy.sh"
  echo "Tip: if Amplify is already connected to your repo, pushing to main can also trigger the frontend deploy."
  exit 1
fi

echo "[amplify] Starting frontend deploy"
echo "[amplify] App ID: ${APP_ID}"
echo "[amplify] Branch: ${BRANCH}"

aws amplify start-job \
  --app-id "${APP_ID}" \
  --branch-name "${BRANCH}" \
  --job-type RELEASE \
  --query 'jobSummary.{JobId:jobId,Status:status,CommitTime:commitTime}' \
  --output table
