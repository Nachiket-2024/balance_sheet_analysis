#!/usr/bin/env bash
# Regression guard for the class of bug found live in this repo three
# separate times in one session: docker/, env/, and scripts/ each got
# split into mystic_auth/ + app/ subfolders, but a comment, doc, or a
# script that builds a path at runtime (rather than a literal, fully
# spelled-out script path token check-script-paths.sh already validates)
# kept referencing the old unsplit location. Each one silently broke a
# real workflow (alembic locally, a Playwright E2E helper, pytest's own
# localhost-derivation) with no error pointing at the actual cause.
#
# check-script-paths.sh already validates every scripts/local-scripts/
# path ending in .sh/.py/.ps1/.cmd/.bat actually exists. This script
# covers what that one can't: literal pre-split path substrings
# (env/.env, docker/compose/, docker/dockerfiles/, docker/postgres-init/,
# docker/Caddyfile, docker/nginx.frontend.conf) appearing anywhere in
# source, scripts, or docs - these don't reliably end in a checkable file
# extension (a .yml Dockerfile path, a bare directory reference in a
# comment), so an existence check can't catch them; a denylist can.
#
# Excluded on purpose, same reasoning as check-script-paths.sh:
#   - This script's own file: the patterns list below necessarily
#     contains the literal strings being searched for.
#   - docs/mystic_auth/project-story/ and docker/validation-history.md:
#     historical narrative describing paths as they were at the time.
#   - tests/scripts/mystic_auth/upstream-sync/test-sync-upstream.sh:
#     builds its own fixture repo with pre-split paths on purpose, to
#     simulate a consumer syncing from an old template version.
#   - tests/scripts/mystic_auth/lint/check-script-paths.sh: its own
#     docstring names the real pre-split paths from the bug it was built
#     to catch, as history, not a live reference.
#
# Usage: tests/scripts/mystic_auth/lint/check-split-paths.sh
# Exit 0: no pre-split path found. Exit 1: one or more found, listed.
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
cd "$REPO_ROOT"

SELF="tests/scripts/mystic_auth/lint/check-split-paths.sh"

# Order matters for readability in output only. grep -F below treats each
# as a literal string, not a pattern.
PATTERNS=(
  'env/.env'
  'docker/compose/'
  'docker/dockerfiles/'
  'docker/postgres-init/'
  'docker/Caddyfile'
  'docker/nginx.frontend.conf'
  'scripts/env-tools/'
  'scripts/docker/'
  'scripts/upstream-sync/'
  'scripts/db/'
  'scripts/load-test/'
)

# git ls-files (tracked + untracked-but-not-ignored), not find: skips
# gitignored files (a personal AGENTS.md/CLAUDE.md, generated
# env/mystic_auth/.env.dev, etc.) that aren't part of what actually ships,
# and would otherwise show up as false positives, while still covering a
# file that's new on disk but not committed yet.
FILES=()
while IFS= read -r f; do
  case "$f" in
    "$SELF") continue ;;
    docs/mystic_auth/project-story/*) continue ;;
    docs/mystic_auth/docker/validation-history.md) continue ;;
    tests/scripts/mystic_auth/upstream-sync/test-sync-upstream.sh) continue ;;
    tests/scripts/mystic_auth/lint/check-script-paths.sh) continue ;;
    *.py|*.ts|*.tsx|*.sh|*.ps1|*.cmd|*.bat|*.md|*.yml|*.yaml) FILES+=("$f") ;;
    */Makefile|Makefile) FILES+=("$f") ;;
  esac
done < <(git ls-files --cached --others --exclude-standard)

HITS=()

for f in "${FILES[@]}"; do
  for pattern in "${PATTERNS[@]}"; do
    # -F: literal string, not regex. env/.env would otherwise also match
    # env/mystic_auth/.env.dev via the "." wildcard if treated as a regex.
    while IFS= read -r line; do
      [ -n "$line" ] || continue
      # A real "env/mystic_auth/.env.dev" or "env/app/.env.dev" substring contains
      # "env/.env" only as a false positive of the plain-string search
      # above when "mystic_auth/.env" or "app/.env" is what's actually
      # there - filter those back out here.
      if [ "$pattern" = "env/.env" ]; then
        case "$line" in
          *env/mystic_auth/.env*|*env/app/.env*) continue ;;
        esac
      fi
      HITS+=("$f: $pattern")
      break
    done < <(grep -F "$pattern" "$f" 2>/dev/null)
  done
done

if [ "${#HITS[@]}" -eq 0 ]; then
  echo "OK: no pre-split docker/env/scripts path reference found."
  exit 0
fi

echo "ERROR: ${#HITS[@]} pre-split path reference(s) found:"
echo
printf '  %s\n' "${HITS[@]}"
echo
echo "docker/, env/, and scripts/ each split into mystic_auth/ + app/"
echo "subfolders. A reference above still points at the old unsplit"
echo "location - update it, or add it to this script's excluded-files"
echo "list if it's deliberately historical."
exit 1
