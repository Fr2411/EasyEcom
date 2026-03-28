#!/usr/bin/env bash
set -euo pipefail

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "[repo-surface] not inside a git work tree" >&2
  exit 2
fi

readonly -a forbidden_patterns=(
  '^\.venv[^/]*(/|$)'
  '^\.idea(/|$)'
  '^server\.log$'
  '(^|/).*\.(bak|backup|backup2|debug|orig|work)$'
  '^frontend/tsconfig\.tsbuildinfo$'
  '^frontend/\.next(/|$)'
  '^frontend/node_modules(/|$)'
  '(^|/)__pycache__(/|$)'
  '^.*\.egg-info(/|$)'
)

violations=()

while IFS= read -r file; do
  if [[ -z "$file" ]]; then
    continue
  fi
  for pattern in "${forbidden_patterns[@]}"; do
    if [[ "$file" =~ $pattern ]]; then
      violations+=("$file")
      break
    fi
  done
done < <(git ls-files)

if ((${#violations[@]} == 0)); then
  echo "[repo-surface] clean"
  exit 0
fi

unique_violations=$(printf '%s\n' "${violations[@]}" | sort -u)
total_violations=$(printf '%s\n' "${unique_violations}" | sed '/^$/d' | wc -l | tr -d ' ')

printf '[repo-surface] forbidden tracked files found: %s\n' "${total_violations}" >&2
printf '%s\n' "${unique_violations}" | sed -n '1,50p' | sed 's/^/ - /' >&2
if (( total_violations > 50 )); then
  printf ' ... and %s more\n' "$((total_violations - 50))" >&2
fi
exit 1
