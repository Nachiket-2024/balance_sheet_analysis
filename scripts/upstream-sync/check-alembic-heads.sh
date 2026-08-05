#!/usr/bin/env bash
# Detects multiple alembic heads by statically parsing
# backend/alembic/versions/*.py -- no python/alembic install, venv, or
# running database needed, so this works from a bare git checkout.
#
# Two heads happen when the template and a downstream app each add a
# migration on the same fork point: both point their down_revision at the
# same old revision, so neither is anyone else's parent. `alembic upgrade
# head` doesn't catch this ahead of time -- it fails at deploy/migrate time
# with "Multiple head revisions are present". This catches it right after a
# sync instead.
#
# Usage: scripts/upstream-sync/check-alembic-heads.sh
# Exit 0: single head (or no migrations yet). Exit 1: 2+ heads, details printed.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VERSIONS_DIR="$REPO_ROOT/backend/alembic/versions"

if [ ! -d "$VERSIONS_DIR" ]; then
  echo "No $VERSIONS_DIR directory -- nothing to check."
  exit 0
fi

shopt -s nullglob
VERSION_FILES=("$VERSIONS_DIR"/*.py)
shopt -u nullglob

if [ "${#VERSION_FILES[@]}" -eq 0 ]; then
  echo "No migration files under $VERSIONS_DIR -- nothing to check."
  exit 0
fi

# Pulls every quoted token off a `revision = ...` / `down_revision = ...`
# line -- handles both single revisions and the tuple form
# (`down_revision = ('a', 'b')`) that alembic itself writes for merge
# migrations, without needing to parse Python.
extract_ids() {
  # `|| true`: no match (e.g. `down_revision = None`) is a normal case here,
  # not an error -- without it, `set -e` + `pipefail` would kill the whole
  # script the first time a migration with no parent (like the initial one)
  # got scanned.
  # `paste -sd' ' -`: grep -o prints each match on its own line, but callers
  # fold this into a space-delimited string (`ALL_DOWN_REVISIONS="$ALL_DOWN_REVISIONS $(...)"`)
  # and match against it with `*" $REV "*` -- a tuple's second-and-later IDs
  # need a real space before them, not the newline grep -o would leave. Using
  # `paste` (rather than `tr '\n' ' '`) avoids a trailing space, which would
  # otherwise corrupt single-ID `REV` values used as associative-array keys.
  grep -oE "['\"][a-f0-9]{6,}['\"]" <<<"$1" | tr -d "'\"" | paste -sd' ' - || true
}

ALL_REVISIONS=""
ALL_DOWN_REVISIONS=""
declare -A REVISION_FILE
declare -A REVISION_MESSAGE

for f in "${VERSION_FILES[@]}"; do
  REV_LINE="$(grep -m1 '^revision' "$f" || true)"
  DOWN_LINE="$(grep -m1 '^down_revision' "$f" || true)"
  [ -z "$REV_LINE" ] && continue

  REV="$(extract_ids "$REV_LINE")"
  [ -z "$REV" ] && continue

  # First line of the migration docstring (alembic writes it on line 1,
  # right after the opening `"""`), used only to make the error output
  # readable -- falls back to the filename if the docstring is missing or
  # oddly formatted.
  MSG="$(sed -n '1s/^"""//p' "$f" | sed 's/^ *//;s/ *$//')"
  [ -z "$MSG" ] && MSG="$(basename "$f")"

  ALL_REVISIONS="$ALL_REVISIONS $REV"
  REVISION_FILE["$REV"]="$f"
  REVISION_MESSAGE["$REV"]="$MSG"

  if [ -n "$DOWN_LINE" ]; then
    ALL_DOWN_REVISIONS="$ALL_DOWN_REVISIONS $(extract_ids "$DOWN_LINE")"
  fi
done

HEADS=()
for REV in $ALL_REVISIONS; do
  case " $ALL_DOWN_REVISIONS " in
    *" $REV "*) ;; # referenced as someone's down_revision -- not a head
    *) HEADS+=("$REV") ;;
  esac
done

if [ "${#HEADS[@]}" -le 1 ]; then
  echo "OK: single alembic head${HEADS:+ ($HEADS)}."
  exit 0
fi

echo "ERROR: multiple alembic heads detected (${#HEADS[@]}):"
echo ""
for REV in "${HEADS[@]}"; do
  echo "  $REV  ${REVISION_MESSAGE[$REV]}"
  echo "    ${REVISION_FILE[$REV]#"$REPO_ROOT/"}"
done
cat <<EOF

This usually means the template and this app each added a migration on top
of the same fork point -- two chains now claim to be the latest, and
"alembic upgrade head" will refuse to run ("Multiple head revisions are
present") until this is resolved.

Fix it with a merge migration (needs a real alembic install, e.g. inside the
backend container):

  docker compose exec backend alembic merge heads -m "merge migration branches"

That generates one new file whose down_revision is both heads above -- commit
it like any other migration. See docs/mystic_auth/template-usage/syncing-upstream.md
for when this runs and why.
EOF
exit 1
