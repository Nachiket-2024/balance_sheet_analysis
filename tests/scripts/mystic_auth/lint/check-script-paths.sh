#!/usr/bin/env bash
# Regression guard for exactly the class of bug found live in this repo:
# quickstart.sh/quickstart.ps1 called `./scripts/env-tools/...` and
# `./scripts/docker/...` (missing the `mystic_auth/` segment) after an
# earlier restructuring commit, so the #1 command in README.md failed on
# line 1 for every new user. Nothing caught that until someone actually ran
# it by hand.
#
# Scans every CI, script (.sh/.ps1/.cmd/.bat), Makefile (root and
# makefiles/*/), and doc (.md) for a path token containing `ci/`,
# `scripts/`, or `local-scripts/` and ending in
# .sh/.py/.ps1/.cmd/.bat (forward-slash or backslash), and asserts the
# target file actually exists. Matches the whole contiguous path token
# (e.g. `backend/mystic_auth/scripts/create_system_user.py`), not just the
# `scripts/...` suffix, so a real path with more segments before `scripts/`
# isn't misreported as missing.
#
# Also scans every Dockerfile's `COPY <src> ...` lines (skipping
# `--from=` multi-stage copies) and asserts each source exists relative
# to the repo root - `docker compose config` never checks these.
#
# Excluded on purpose:
#   - This script's own file: its usage comment uses placeholder example
#     paths that don't exist by design.
#   - docs/mystic_auth/project-story/ and docker/validation-history.md:
#     historical narrative describing paths as they were at the time, not
#     the current tree - "fixing" these would misrepresent history.
#   - tests/scripts/mystic_auth/upstream-sync/test-sync-upstream.sh:
#     creates its own fixture paths dynamically inside a temp sandbox
#     repo, never in this repo's tree.
#
# Usage: tests/scripts/mystic_auth/lint/check-script-paths.sh
# Exit 0: every referenced path resolves. Exit 1: one or more don't, listed.
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
cd "$REPO_ROOT"

SELF="tests/scripts/mystic_auth/lint/check-script-paths.sh"

FILES=()
while IFS= read -r -d '' f; do
  case "$f" in
    "$SELF") continue ;;
    docs/mystic_auth/project-story/*) continue ;;
    docs/mystic_auth/docker/validation-history.md) continue ;;
    tests/scripts/mystic_auth/upstream-sync/test-sync-upstream.sh) continue ;;
  esac
  FILES+=("$f")
done < <(
  find ci scripts local-scripts tests/scripts docs agent-prompts makefiles -type f \
    \( -name "*.sh" -o -name "*.ps1" -o -name "*.cmd" -o -name "*.bat" -o -name "*.md" -o -name "Makefile" \) \
    -print0
  find . -maxdepth 1 \( -name "*.md" -o -name "Makefile" -o -name "make.ps1" \) -print0
)

MISSING=()

for f in "${FILES[@]}"; do
  while IFS= read -r token; do
    [ -n "$token" ] || continue
#     Only tokens that actually contain a ci/, scripts/, or local-scripts/ path
    # component (forward or backslash) are in scope.
    case "$token" in
      *ci/*|*ci\\*|*scripts/*|*scripts\\*) ;;
      *) continue ;;
    esac
    normalized="${token#./}"
    normalized="${normalized#.\\}"
    normalized="${normalized//\\//}"
    if [ ! -f "$normalized" ]; then
      MISSING+=("$f: $token")
    fi
  done < <(grep -oP '(?<![A-Za-z0-9_$}])[A-Za-z0-9_./\\-]*\.(sh|py|ps1|cmd|bat)' "$f" 2>/dev/null | sort -u)
done

while IFS= read -r -d '' f; do
  while IFS= read -r src; do
    [ -n "$src" ] || continue
    # COPY sources can be a glob (e.g. package*.json); compgen expands it
    # against the real filesystem instead of treating it as a literal path.
    if [ -f "$src" ] || [ -d "$src" ]; then
      continue
    fi
    compgen -G "$src" >/dev/null 2>&1 || MISSING+=("$f: COPY $src")
  done < <(grep -oP '^\s*COPY\s+(?!--from)\K\S+' "$f" 2>/dev/null | sort -u)
done < <(find docker -type f \( -iname "*.Dockerfile" -o -iname "Dockerfile" -o -iname "Dockerfile.*" \) -print0)

# A fresh GitHub checkout invokes CI entry points directly. The filesystem
# mode may look executable in a local WSL working tree while the Git index
# still records 100644, which makes the same command fail after checkout.
NON_EXECUTABLE_SHELL_FILES=()
while IFS= read -r path; do
  [ -n "$path" ] || continue
  NON_EXECUTABLE_SHELL_FILES+=("$path")
done < <(
  git ls-files -s -- '*.sh' \
    | awk '$1 != "100755" { print $4 }'
)

if [ "${#NON_EXECUTABLE_SHELL_FILES[@]}" -ne 0 ]; then
  echo "ERROR: ${#NON_EXECUTABLE_SHELL_FILES[@]} tracked shell script(s) are not executable in the Git index:"
  printf '  %s\n' "${NON_EXECUTABLE_SHELL_FILES[@]}"
  echo
  echo "Run chmod +x on each file, stage the mode change, and re-run this check."
  exit 1
fi

if [ "${#MISSING[@]}" -eq 0 ]; then
  echo "OK: every path reference resolves and every tracked shell script is executable in the Git index."
  exit 0
fi

echo "ERROR: ${#MISSING[@]} dangling script reference(s) found:"
echo
printf '  %s\n' "${MISSING[@]}"
echo
echo "A script or doc points at a path that doesn't exist - likely a stale"
echo "reference left over from a rename/restructure. Fix the path or the"
echo "target, then re-run this check."
exit 1
