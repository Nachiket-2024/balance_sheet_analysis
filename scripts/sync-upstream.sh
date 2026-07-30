#!/usr/bin/env bash
# On-demand: pulls in updates from the original mystic-auth template repo.
# Nothing here runs automatically -- this only does anything when you run it.
# See docs/mystic_auth/template-usage/syncing-upstream.md for the full
# explanation of what conflicts and what almost never will.
#
# Two sync strategies, chosen automatically:
#
#   1. First sync ever (no .mystic-auth-sync-state file yet): a whole-tree
#      `git merge --squash --allow-unrelated-histories`. This never records
#      upstream's commits as ancestors of your history -- your `git log`
#      stays just your own commits plus one "synced upstream" commit.
#   2. Every sync after that: an incremental `git diff <last-synced-sha>
#      upstream/branch | git apply --3way`. This is NOT the same algorithm
#      run again -- `--squash` has no merge-base to work from (unrelated
#      histories), so on a second squash-merge git re-diffs the ENTIRE tree
#      against nothing, and any file upstream touched can conflict even if
#      you never touched it. The incremental diff has a real baseline (the
#      exact upstream commit recorded last time), so it only contains what
#      actually changed since then -- a file neither side touched produces
#      zero diff. `--3way` is what keeps today's conflict UX: a hunk that
#      doesn't apply cleanly (i.e. you hand-edited that file) falls back to
#      a real 3-way merge with normal <<<<<<< conflict markers, instead of
#      hard-failing the whole patch.
#
# Usage: scripts/sync-upstream.sh [upstream-url]
#   upstream-url defaults to the original template repo; pass your own fork's
#   URL if you're syncing from somewhere else.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

SYNC_STATE_FILE=".mystic-auth-sync-state"
UPSTREAM_URL="${1:-https://github.com/Nachiket-2024/mystic-auth.git}"

if git remote get-url upstream >/dev/null 2>&1; then
  echo "Using existing 'upstream' remote: $(git remote get-url upstream)"
else
  echo "Adding 'upstream' remote: $UPSTREAM_URL"
  git remote add upstream "$UPSTREAM_URL"
fi

echo "Fetching upstream..."
git fetch upstream

# A hiccup on this one metadata call shouldn't abort an otherwise-fine sync,
# so it's not a bare assignment under `set -e` -- fall back to 'main'.
UPSTREAM_BRANCH="$(git remote show upstream 2>/dev/null | sed -n '/HEAD branch/s/.*: //p' || true)"
UPSTREAM_BRANCH="${UPSTREAM_BRANCH:-main}"

UPSTREAM_SHA="$(git rev-parse "upstream/${UPSTREAM_BRANCH}")"
UPSTREAM_SHA_SHORT="${UPSTREAM_SHA:0:7}"

LAST_SYNCED_SHA=""
if [ -f "$SYNC_STATE_FILE" ]; then
  LAST_SYNCED_SHA="$(cat "$SYNC_STATE_FILE")"
fi

# With a recorded baseline, this range is upstream's own ancestry since that
# exact commit -- accurate no matter how many syncs have happened before.
# Without one (first sync ever, or first sync after upgrading from a script
# version that predates this file), there's no baseline to diff from, so this
# lists everything reachable from upstream but not us -- upstream's full
# history, once, same as the old behavior.
if [ -n "$LAST_SYNCED_SHA" ]; then
  INCOMING="$(git log "${LAST_SYNCED_SHA}..upstream/${UPSTREAM_BRANCH}" --oneline)"
else
  INCOMING="$(git log "HEAD..upstream/${UPSTREAM_BRANCH}" --oneline)"
fi

if [ -z "$INCOMING" ]; then
  echo "Already up to date with upstream/${UPSTREAM_BRANCH}."
  exit 0
fi

echo ""
echo "Incoming commits from upstream/${UPSTREAM_BRANCH}:"
echo "$INCOMING"
echo ""

read -r -p "Sync these into the current branch now? [y/N] " CONFIRM
case "$CONFIRM" in
  [yY]|[yY][eE][sS]) ;;
  *) echo "Not syncing. Run this script again whenever you're ready."; exit 0 ;;
esac

SYNC_LOG="$(mktemp)"
PATCH_FILE="$(mktemp)"
trap 'rm -f "$SYNC_LOG" "$PATCH_FILE"' EXIT

CONFLICT=0

if [ -z "$LAST_SYNCED_SHA" ]; then
  if ! git merge "upstream/${UPSTREAM_BRANCH}" --squash --allow-unrelated-histories >"$SYNC_LOG" 2>&1; then
    cat "$SYNC_LOG"
    if grep -q "CONFLICT" "$SYNC_LOG"; then
      CONFLICT=1
    else
      exit 1
    fi
  else
    cat "$SYNC_LOG"
  fi
else
  git diff --binary "$LAST_SYNCED_SHA" "upstream/${UPSTREAM_BRANCH}" > "$PATCH_FILE"
  if ! git apply --3way --index "$PATCH_FILE" >"$SYNC_LOG" 2>&1; then
    cat "$SYNC_LOG"
    # `git apply --3way` leaves unmerged index entries for genuine conflicts,
    # same signal a real merge would give -- anything else is a real failure.
    if [ -n "$(git ls-files -u)" ]; then
      CONFLICT=1
    else
      exit 1
    fi
  else
    cat "$SYNC_LOG"
  fi
fi

# Record the upstream commit this sync brought us to, regardless of which
# path ran or whether it ended clean or conflicted -- resolving a conflict
# by hand still means "we've now incorporated upstream up to this SHA".
echo "$UPSTREAM_SHA" > "$SYNC_STATE_FILE"
git add "$SYNC_STATE_FILE"

if [ "$CONFLICT" -eq 1 ]; then
  echo ""
  echo "Conflicts staged above -- resolve them in your working tree, then:"
  echo "  git add <resolved files>"
  echo "  git commit -m \"Sync upstream template updates (mystic-auth@${UPSTREAM_SHA_SHORT})\""
  echo "(${SYNC_STATE_FILE} is already staged with the new upstream commit -- nothing to do for it.)"
  exit 1
fi

git commit -m "Sync upstream template updates (mystic-auth@${UPSTREAM_SHA_SHORT})"

cat <<EOF

Synced and committed as a single commit (mystic-auth@${UPSTREAM_SHA_SHORT}).
Your history stays yours -- no upstream commits were imported.

Before trusting this, rebuild and rerun the test suite -- a sync can change
behavior underneath you even when every file merged automatically:

  docker compose up -d --build
  docker compose exec --user root -w /repo backend python -m pytest tests/backend/mystic_auth/unit tests/backend/mystic_auth/integration tests/backend/mystic_auth/security
  # frontend: see docs/mystic_auth/testing/overview.md for the equivalent commands
  # --user root is needed on native Linux, or pytest-cov's coverage output
  # crashes with a permission error. On Windows with Git Bash, the command
  # above can separately fail with "Cwd must be an absolute path" instead --
  # see docs/mystic_auth/docker/overview.md#running-a-one-off-command-inside-a-container
  # for both.
EOF
