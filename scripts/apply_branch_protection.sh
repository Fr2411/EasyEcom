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

if ! command -v jq >/dev/null 2>&1; then
  echo "[branch-protection] jq is required" >&2
  exit 1
fi

REPO="${GITHUB_REPOSITORY:-$(gh repo view --json nameWithOwner -q .nameWithOwner)}"
CHECK_NAME="Staging Policy Gate / verify"

apply_protection() {
  local branch="$1"
  echo "[branch-protection] Applying protection on ${REPO}:${branch}"

  local payload
  payload="$(jq -n --arg check_name "${CHECK_NAME}" '
    {
      required_status_checks: {
        strict: true,
        contexts: [$check_name]
      },
      enforce_admins: true,
      required_pull_request_reviews: {
        dismiss_stale_reviews: true,
        require_code_owner_reviews: false,
        required_approving_review_count: 1
      },
      restrictions: null,
      allow_force_pushes: false,
      allow_deletions: false,
      required_linear_history: true,
      block_creations: false
    }
  ')"

  gh api \
    --method PUT \
    -H "Accept: application/vnd.github+json" \
    -H "X-GitHub-Api-Version: 2022-11-28" \
    "repos/${REPO}/branches/${branch}/protection" \
    --input - <<<"${payload}"
}

apply_protection main
apply_protection develop

echo "[branch-protection] Done"
