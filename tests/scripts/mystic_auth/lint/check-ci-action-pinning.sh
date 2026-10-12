#!/usr/bin/env bash
# Regression guard for mutable GitHub Action references. A moved tag changes
# what code runs without changing the workflow's reference.
#
# Asserts every `uses: owner/repo@ref` in .github/workflows/*.yml is pinned
# by a 40-character commit SHA.
#
# Usage: tests/scripts/mystic_auth/lint/check-ci-action-pinning.sh
# Exit 0: every action is SHA-pinned. Exit 1: one or more aren't, listed.
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
cd "$REPO_ROOT"

BAD=()

while IFS= read -r -d '' f; do
  while IFS=: read -r line_no ref; do
    [ -n "$ref" ] || continue
    if ! [[ "$ref" =~ ^[0-9a-f]{40}$ ]]; then
      BAD+=("$f:$line_no: action pinned by '$ref', not a 40-character commit SHA")
    fi
  done < <(grep -noP '(?<=uses:\s*)[^\s@]+@\K[^\s#]+' "$f" 2>/dev/null)
done < <(find .github/workflows -type f -name "*.yml" -print0 2>/dev/null)

if [ "${#BAD[@]}" -eq 0 ]; then
  echo "OK: every third-party action in .github/workflows/*.yml is pinned by commit SHA."
  exit 0
fi

echo "ERROR: ${#BAD[@]} action(s) not pinned by commit SHA:"
echo
printf '  %s\n' "${BAD[@]}"
echo
echo "Resolve the tag to a commit SHA with:"
echo "  gh api repos/<owner>/<repo>/git/refs/tags/<tag> --jq '.object.sha'"
echo "and pin as 'uses: owner/repo@<sha> # <tag>' so the human-readable version stays visible."
exit 1
