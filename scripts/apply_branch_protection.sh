#!/usr/bin/env bash
set -euo pipefail

if ! command -v gh >/dev/null 2>&1; then
  echo "[branch-protection] GitHub CLI (gh) is required" >&2
  exit 1
fi

if ! gh auth status >/dev/null 2>&1; then
  echo "[branch-protection] gh is not authenticated. Run: gh auth login" >&2
  exit 1
fi

REPO="${GITHUB_REPOSITORY:-$(gh repo view --json nameWithOwner -q .nameWithOwner)}"
CHECK_NAME="Staging Policy Gate / verify"

apply_protection() {
  local branch="$1"
  echo "[branch-protection] Applying protection on ${REPO}:${branch}"

  gh api \
    --method PUT \
    -H "Accept: application/vnd.github+json" \
    "repos/${REPO}/branches/${branch}/protection" \
    -f required_status_checks.strict=true \
    -f required_status_checks.contexts[]="${CHECK_NAME}" \
    -f enforce_admins=true \
    -f required_pull_request_reviews.required_approving_review_count=1 \
    -f required_pull_request_reviews.dismiss_stale_reviews=true \
    -f required_pull_request_reviews.require_code_owner_reviews=false \
    -f restrictions= \
    -f allow_force_pushes=false \
    -f allow_deletions=false \
    -f required_linear_history=true \
    -f block_creations=false
}

apply_protection main
apply_protection develop

echo "[branch-protection] Done"
