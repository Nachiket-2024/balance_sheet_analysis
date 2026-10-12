#!/usr/bin/env bash
# On-demand: pulls in updates from the original mystic-auth template repo.
# Nothing here runs automatically. See
# docs/mystic_auth/template-usage/syncing-upstream/README.md for what conflicts and
# what almost never will.
#
# Two sync strategies, chosen automatically:
#
#   1. First sync ever (no .mystic-auth-sync-state file yet): a whole-tree
#      `git merge --squash --allow-unrelated-histories`, so upstream's own
#      commits never become ancestors of your history.
#   2. Every sync after: an incremental `git diff <last-synced-sha>
#      upstream/branch | git apply --3way`. Squash has no merge-base on
#      unrelated histories so it re-diffs the whole tree every time; the
#      incremental diff has a real baseline, so an untouched file produces
#      zero diff instead of a phantom conflict. `--3way` turns an unclean
#      hunk into a real 3-way merge with conflict markers instead of
#      hard-failing the patch.
#
# Three safety nets run after either strategy, before anything commits:
#   - A "did anything actually change" check: `git apply`/`git merge` can
#     report success while one file (a binary file is the sharpest example)
#     silently fails to apply. Compares the file list the diff says should
#     have changed against what's actually staged/conflicted, and refuses to
#     commit on a mismatch.
#   - An executable-bit self-heal for scripts/**/*.sh (see the comment at
#     that check below for why this runs every sync, not just once).
#   - scripts/mystic_auth/upstream-sync/check-alembic-heads.sh: catches this app and
#     upstream both adding a migration on the same fork point, which
#     otherwise stays silent until `alembic upgrade head` fails at deploy time.
#
# Also enables `git rerere`: once a conflict is resolved by hand, git
# reapplies that resolution if the same-shaped conflict recurs, which happens
# often when upstream rewords a comment next to your own edit.
#
# Usage: scripts/mystic_auth/upstream-sync/sync-upstream.sh [upstream-url]
#   upstream-url defaults to the original template repo; pass your own fork's
#   URL if you're syncing from somewhere else.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$REPO_ROOT"

# The sync uses the existing index as its merge/apply workspace and commits
# that index at the end. Staged downstream work would therefore be swept into
# the sync commit, so fail before fetching or changing anything.
if ! git diff --cached --quiet --ignore-submodules --; then
  echo "ERROR: the Git index contains staged changes." >&2
  echo "Commit or unstage downstream work before running sync-upstream.sh; the sync commit must contain sync changes only." >&2
  exit 1
fi

git config rerere.enabled true

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

# With a recorded baseline, this is upstream's ancestry since that exact
# commit. Without one (first sync, or upgrading from a pre-state-file
# version), there's nothing to diff from, so this lists upstream's full
# history instead -- same as a first sync.
if [ -n "$LAST_SYNCED_SHA" ]; then
  INCOMING="$(git log "${LAST_SYNCED_SHA}..upstream/${UPSTREAM_BRANCH}" --oneline)"
else
  INCOMING="$(git log "HEAD..upstream/${UPSTREAM_BRANCH}" --oneline)"
fi

if [ -z "$INCOMING" ]; then
  echo "Already up to date with upstream/${UPSTREAM_BRANCH}."
  exit 0
fi

if [ -n "$LAST_SYNCED_SHA" ]; then
  UPSTREAM_PATH_CHANGES="$(git diff --name-status -M "$LAST_SYNCED_SHA" "upstream/${UPSTREAM_BRANCH}")"
else
  UPSTREAM_PATH_CHANGES="$(git diff --name-status -M --diff-filter=ACMR HEAD "upstream/${UPSTREAM_BRANCH}")"
fi

# A fork-owned path must never arrive from upstream. Shared files such as
# backend/app/main.py remain intentionally extend-in-place and are not in this
# list. Blocking here catches an accidental upstream edit before a merge can
# silently overwrite downstream product code.
#
# Reference tests that shipped in an older template may already live under
# tests/**/app/. If the same test path was present in the recorded upstream
# baseline (or in both trees during a first sync), an upstream fix to that
# inherited test is a legitimate template update. Three-way apply still
# exposes downstream customization as a conflict; newly added downstream
# tests remain blocked.
if [ -n "$LAST_SYNCED_SHA" ]; then
  APP_OWNED_DIFF="$(git diff --name-only "$LAST_SYNCED_SHA" "upstream/${UPSTREAM_BRANCH}")"
else
  # Unrelated first-sync histories show consumer-only files as deletions on
  # the upstream side. They are not incoming changes and must not be reported
  # as ownership violations (especially when an app split was stashed).
  APP_OWNED_DIFF="$(git diff --name-only --diff-filter=ACMR HEAD "upstream/${UPSTREAM_BRANCH}")"
fi
APP_OWNED_PATH_CHANGES=""

# The CI split was introduced after some downstream projects already existed.
# Allow the three initial app CI entrypoints to be added once when neither the
# consumer's current tree nor its recorded sync baseline has them. After that
# first adoption, normal app-owned protection applies and upstream cannot edit
# them.
is_ci_app_bootstrap_path() {
  local path="$1"
  case "$path" in
    ci/app/backend.sh|ci/app/frontend.sh|ci/app/frontend-e2e.sh) ;;
    *) return 1 ;;
  esac

  if [ -n "$LAST_SYNCED_SHA" ]; then
    git cat-file -e "${LAST_SYNCED_SHA}:${path}" 2>/dev/null && return 1
  else
    git cat-file -e "HEAD:${path}" 2>/dev/null && return 1
  fi
  return 0
}

while IFS= read -r changed_path; do
  [ -z "$changed_path" ] && continue

  if [[ "$changed_path" == tests/*/app/* ]]; then
    if [ -n "$LAST_SYNCED_SHA" ]; then
      git cat-file -e "${LAST_SYNCED_SHA}:${changed_path}" 2>/dev/null &&
        git cat-file -e "upstream/${UPSTREAM_BRANCH}:${changed_path}" 2>/dev/null &&
        continue
    else
      git cat-file -e "HEAD:${changed_path}" 2>/dev/null &&
        git cat-file -e "upstream/${UPSTREAM_BRANCH}:${changed_path}" 2>/dev/null &&
        continue
    fi
  fi

  case "$changed_path" in
    backend/app/main.py|backend/app/sdk.py|frontend/src/app/App.tsx|frontend/src/app/sdk.ts)
      continue
      ;;
    frontend/src/app/main.tsx|frontend/src/app/theme.ts)
      # These app-owned shell files may receive comment-only template cleanup.
      # Keep behavior and product changes under the normal app-ownership guard.
      ownership_base="${LAST_SYNCED_SHA:-HEAD}"
      if git cat-file -e "${ownership_base}:${changed_path}" 2>/dev/null \
        && git cat-file -e "upstream/${UPSTREAM_BRANCH}:${changed_path}" 2>/dev/null \
        && git diff --unified=0 "$ownership_base" "upstream/${UPSTREAM_BRANCH}" -- "$changed_path" \
          | awk '
            /^\+\+\+|^---/ { next }
            /^[+-]/ {
              line = substr($0, 2)
              if (line ~ /^[[:space:]]*$/) next
              if (line !~ /^[[:space:]]*(\/\/|\/\*|\*\/|\*)/) invalid = 1
            }
            END { exit invalid ? 1 : 0 }
          '; then
        continue
      fi
      APP_OWNED_PATH_CHANGES+="${changed_path}"$'\n'
      ;;
    ci/app/*)
      is_ci_app_bootstrap_path "$changed_path" || APP_OWNED_PATH_CHANGES+="${changed_path}"$'\n'
      ;;
    backend/app/*|frontend/src/app/*|tests/*/app/*|docs/app/*|screenshots/app/*|scripts/app/*|agent-prompts/app/*|local-scripts/app/*|docker/app/*|env/app/*|makefiles/app/*)
      APP_OWNED_PATH_CHANGES+="${changed_path}"$'\n'
      ;;
  esac
done <<< "$APP_OWNED_DIFF"
APP_OWNED_PATH_CHANGES="${APP_OWNED_PATH_CHANGES%$'\n'}"
if [ -n "$APP_OWNED_PATH_CHANGES" ]; then
  echo "ERROR: upstream attempted to change downstream-owned paths:" >&2
  printf '%s\n' "$APP_OWNED_PATH_CHANGES" | sed 's/^/  /' >&2
  echo "Resolve the ownership violation upstream before syncing; this script will not apply it." >&2
  exit 1
fi

# Root README/security/contribution files are downstream-owned starting
# points, but upstream's own copies may still improve over time. Preserve the
# downstream copies while allowing unrelated upstream changes to sync; the
# filtered diff below excludes them from both the expected-file check and the
# applied patch.
IGNORED_ROOT_DOC_CHANGES="$(git diff --name-only "$([ -n "$LAST_SYNCED_SHA" ] && echo "$LAST_SYNCED_SHA" || echo HEAD)" "upstream/${UPSTREAM_BRANCH}" -- README.md SECURITY.md CONTRIBUTING.md)"
if [ -n "$IGNORED_ROOT_DOC_CHANGES" ]; then
  echo "Ignoring upstream changes to downstream-owned root docs (local copies preserved):"
  printf '%s\n' "$IGNORED_ROOT_DOC_CHANGES" | sed 's/^/  /'
fi

echo ""
echo "Incoming commits from upstream/${UPSTREAM_BRANCH}:"
echo "$INCOMING"
echo ""

REMOVAL_OR_RENAME_CHANGES="$(printf '%s\n' "$UPSTREAM_PATH_CHANGES" | awk '$1 == "D" || $1 ~ /^R[0-9]+$/')"
if [ -n "$REMOVAL_OR_RENAME_CHANGES" ]; then
  echo "Upstream file removals/renames in this sync (old paths will not be kept):"
  printf '%s\n' "$REMOVAL_OR_RENAME_CHANGES" | while IFS= read -r change; do
    case "$change" in
      D$'\t'*) printf '  DELETE %s\n' "${change#*$'\t'}" ;;
      R*$'\t'*)
        old_path="${change#*$'\t'}"
        new_path="${old_path#*$'\t'}"
        old_path="${old_path%%$'\t'*}"
        printf '  MOVE   %s -> %s\n' "$old_path" "$new_path"
        ;;
    esac
  done
  echo "These upstream-owned paths are included in the sync and will be removed or moved as shown."
  echo "The ownership split normally keeps app-owned paths out of upstream changes; inspect any app-owned path if one appears unexpectedly."
  echo ""
fi

# A normal 3-way patch is the wrong primitive for an upstream-owned rename or
# deletion: git apply can require the old path to exist in the consumer index,
# even when the consumer already removed it locally. Handle these structural
# changes from the upstream tree after applying the ordinary patch. The
# ownership guard above has already rejected app-owned paths; root docs are
# intentionally preserved and therefore stay in the ordinary exclusion list.
STRUCTURAL_PATH_ARGS=()
if [ -n "$LAST_SYNCED_SHA" ]; then
  while IFS=$'\t' read -r change_status old_path new_path; do
    [ -n "$change_status" ] || continue
    case "$change_status" in
      D)
        structural_path="$old_path"
        ;;
      R[0-9]*)
        structural_path="$old_path"
        ;;
      *)
        continue
        ;;
    esac
    case "$structural_path" in
      README.md|SECURITY.md|CONTRIBUTING.md) continue ;;
    esac
    if [[ "$change_status" == D ]] \
      && git ls-files --error-unmatch -- "$old_path" >/dev/null 2>&1 \
      && ! git diff --quiet "$LAST_SYNCED_SHA" -- "$old_path"; then
      # A locally modified deletion must remain on the normal patch path so
      # git can surface a conflict instead of silently discarding the edit.
      continue
    fi
    # If the old rename source still exists in the consumer index, let the
    # normal 3-way apply surface a conflict/hard failure so local edits cannot
    # be overwritten implicitly. Direct handling is only for a source path
    # that is already absent, the case git apply cannot represent reliably.
    if [[ "$change_status" == R* ]] && git ls-files --error-unmatch -- "$old_path" >/dev/null 2>&1; then
      continue
    fi
    STRUCTURAL_PATH_ARGS+=(":!$structural_path")
    if [[ "$change_status" == R* ]]; then
      case "$new_path" in
        README.md|SECURITY.md|CONTRIBUTING.md) continue ;;
      esac
      STRUCTURAL_PATH_ARGS+=(":!$new_path")
    fi
  done <<< "$UPSTREAM_PATH_CHANGES"
fi

read -r -p "Sync these into the current branch now? [y/N] " CONFIRM
case "$CONFIRM" in
  [yY]|[yY][eE][sS]) ;;
  *) echo "Not syncing. Run this script again whenever you're ready."; exit 0 ;;
esac

SYNC_LOG="$(mktemp)"
PATCH_FILE="$(mktemp)"
CONFLICT=0
WORKTREE_STASH_CREATED=0
WORKTREE_STASH_NAME=""

restore_worktree_stash() {
  [ "$WORKTREE_STASH_CREATED" -eq 1 ] || return 0
  echo "Restoring downstream work saved before the sync..."
  if git stash pop; then
    WORKTREE_STASH_CREATED=0
  else
    echo "ERROR: the sync commit succeeded, but the saved downstream work could not be restored cleanly." >&2
    echo "Resolve the restore conflict, then remove the retained stash with: git stash drop" >&2
    return 1
  fi
}

cleanup() {
  local exit_status=$?
  if ! restore_worktree_stash; then
    exit_status=1
  fi
  rm -f "$SYNC_LOG" "$PATCH_FILE"
  exit "$exit_status"
}
trap cleanup EXIT

# What the diff says should change, computed before the apply/merge touches
# anything -- compared against reality afterward to catch a file that
# silently failed to apply despite an overall "success".
if [ -z "$LAST_SYNCED_SHA" ]; then
  # HEAD and upstream/branch are unrelated histories, so a plain `git diff`
  # would list every file that only exists on our side (e.g. this script)
  # as "deleted" -- but the squash-merge doesn't actually delete those, it
  # unions both sides. --diff-filter=ACMR (no D) matches that.
  EXPECTED_FILES="$(git diff --name-only --diff-filter=ACMR HEAD "upstream/${UPSTREAM_BRANCH}" -- . ':!README.md' ':!SECURITY.md' ':!CONTRIBUTING.md' | sort -u)"
else
  EXPECTED_FILES="$(git diff --name-only "$LAST_SYNCED_SHA" "upstream/${UPSTREAM_BRANCH}" -- . ':!README.md' ':!SECURITY.md' ':!CONTRIBUTING.md' "${STRUCTURAL_PATH_ARGS[@]}" | sort -u)"
fi

# The index must be clean because the sync commits it, but downstream users
# often have an app split in the working tree during their first sync. A
# squash merge cannot use HEAD as its index baseline while those unstaged
# deletions or untracked app files are present. Save that work temporarily,
# including untracked app files, apply upstream against a clean tree, then
# restore it after the sync commit. Ignored files such as real env files are
# deliberately excluded from the stash.
if [ -n "$(git status --porcelain --untracked-files=all)" ]; then
  WORKTREE_STASH_NAME="mystic-auth-sync-worktree-$(date +%s)"
  echo "Saving unstaged downstream work while applying the sync: $WORKTREE_STASH_NAME"
  git stash push --include-untracked --message "$WORKTREE_STASH_NAME" >/dev/null
  WORKTREE_STASH_CREATED=1
fi

# A downstream app split can also have removed an upstream-owned path in a
# committed change. In that case the working tree stash is not enough: the
# three-way apply still needs the path's last upstream version in the index.
# Recreate only missing paths that exist in the recorded upstream baseline.
# New files need no base, and structural deletes or renames are handled by
# the direct tree operation below.
if [ -n "$LAST_SYNCED_SHA" ]; then
  while IFS=$'\t' read -r change_status old_path new_path; do
    [ -n "$change_status" ] || continue
    case "$change_status" in
      M|M[0-9]*|C[0-9]*) baseline_path="$old_path" ;;
      *) continue ;;
    esac
    case "$baseline_path" in
      README.md|SECURITY.md|CONTRIBUTING.md) continue ;;
    esac
    if ! git ls-files --error-unmatch -- "$baseline_path" >/dev/null 2>&1 \
      && git cat-file -e "${LAST_SYNCED_SHA}:${baseline_path}" 2>/dev/null; then
      echo "Restoring missing upstream baseline path for three-way apply: $baseline_path"
      git restore --source="$LAST_SYNCED_SHA" --staged --worktree -- "$baseline_path"
    fi
  done <<< "$UPSTREAM_PATH_CHANGES"
fi

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
  git diff --binary "$LAST_SYNCED_SHA" "upstream/${UPSTREAM_BRANCH}" -- . ':!README.md' ':!SECURITY.md' ':!CONTRIBUTING.md' "${STRUCTURAL_PATH_ARGS[@]}" > "$PATCH_FILE"
  if ! git apply --3way --index "$PATCH_FILE" >"$SYNC_LOG" 2>&1; then
    cat "$SYNC_LOG"
    # `git apply --3way` leaves unmerged index entries for genuine conflicts,
    # same signal a real merge would give -- anything else is a real failure.
    if [ -n "$(git ls-files -u)" ]; then
      CONFLICT=1
    else
      # A hard failure with no conflict markers usually means upstream
      # relocated or deleted a file this app customized (e.g. a whole-file
      # rename like docker-compose*.yml -> docker/mystic_auth/compose/*.yml):
      # the patch's
      # delete/create hunk has no matching content on either side to
      # 3-way-merge against, so `git apply` just refuses the whole file
      # instead of leaving something to resolve. Same underlying problem as
      # the "silent partial apply" case below (one file's hunk breaks the
      # apply), but caught here instead because this one fails loudly rather
      # than silently -- so it gets the same "exclude and re-diff" recipe.
      FAILED_PATHS="$(grep -E '^error: ' "$SYNC_LOG" | sed -E 's/^error: ([^:]+):.*/\1/' | sort -u)"
      if [ -n "$FAILED_PATHS" ]; then
        EXCLUDE_ARGS=""
        while IFS= read -r p; do
          EXCLUDE_ARGS="$EXCLUDE_ARGS ':!$p'"
        done <<<"$FAILED_PATHS"
        echo ""
        echo "ERROR: git apply failed outright (no conflict markers) on:"
        echo "$FAILED_PATHS" | sed 's/^/  /'
        echo ""
        echo "This usually means upstream moved or deleted one of these paths (e.g. renamed a file you've customized) and there's nothing on either side for a 3-way merge to reconcile. Nothing has been committed."
        echo "Work around it by re-diffing with the listed path(s) excluded, applying that, then handling the excluded file(s) by hand (diff upstream's old and new location yourself and reapply your customization at the new path):"
        echo "  git diff --binary ${LAST_SYNCED_SHA:-HEAD} upstream/${UPSTREAM_BRANCH} -- .$EXCLUDE_ARGS | git apply --3way --index -"
      fi
      exit 1
    fi
  else
    cat "$SYNC_LOG"
  fi
fi

if [ -n "$LAST_SYNCED_SHA" ] && [ "${#STRUCTURAL_PATH_ARGS[@]}" -gt 0 ]; then
  echo "Applying upstream-owned removals/renames directly from upstream..."
  while IFS=$'\t' read -r change_status old_path new_path; do
    [ -n "$change_status" ] || continue
    case "$change_status" in
      D)
        case "$old_path" in
          README.md|SECURITY.md|CONTRIBUTING.md) continue ;;
        esac
        if git ls-files --error-unmatch -- "$old_path" >/dev/null 2>&1 \
          && ! git diff --quiet "$LAST_SYNCED_SHA" -- "$old_path"; then
          continue
        fi
        echo "  DELETE $old_path"
        git rm -f --ignore-unmatch -- "$old_path"
        ;;
      R[0-9]*)
        case "$old_path:$new_path" in
          README.md:*|SECURITY.md:*|CONTRIBUTING.md:*) continue ;;
          *:README.md|*:SECURITY.md|*:CONTRIBUTING.md) continue ;;
        esac
        if git ls-files --error-unmatch -- "$old_path" >/dev/null 2>&1; then
          continue
        fi
        echo "  MOVE   $old_path -> $new_path"
        git restore --source="upstream/${UPSTREAM_BRANCH}" --staged --worktree -- "$new_path"
        git rm -f --ignore-unmatch -- "$old_path"
        ;;
    esac
  done <<< "$UPSTREAM_PATH_CHANGES"
fi

# Everything that actually shows up as changed: staged (the normal case),
# unstaged (a hunk applying outside the index), and unmerged (a real
# conflict). Any EXPECTED_FILES path missing from all three silently failed
# to apply.
ACTUAL_FILES="$( { git diff --cached --name-only; git diff --name-only; git ls-files -u | cut -f2-; } | sort -u )"
MISSING_FILES="$(comm -23 <(printf '%s\n' "$EXPECTED_FILES") <(printf '%s\n' "$ACTUAL_FILES") | sed '/^$/d')"

if [ -n "$MISSING_FILES" ]; then
  echo ""
  echo "ERROR: the diff said these files should have changed, but none of them show up as changed, staged, or conflicted:"
  echo "$MISSING_FILES" | sed 's/^/  /'
  echo ""
  echo "This is the 'silent partial apply' failure mode -- usually one file in the patch (often a binary file, e.g. a changed screenshot) broke the whole apply without leaving a normal conflict marker behind. Nothing has been committed."
  echo "Work around it by re-diffing with the listed path(s) excluded (':!path' per file), then applying that instead, e.g. for a single file:"
  echo "  git diff --binary ${LAST_SYNCED_SHA:-HEAD} upstream/${UPSTREAM_BRANCH} -- . ':!path/to/the/file' | git apply --3way --index -"
  echo "Then handle the excluded file(s) by hand (e.g. copy the file straight from upstream's working tree)."
  exit 1
fi

# A synced script can land non-executable (mode 100644) on a repo running
# core.filemode=false (the Windows default), since git never diffs a
# mode-only change there. Fixed unconditionally rather than relying on a
# human to notice. Stage 0 only (`$3 == "0"`), so an unresolved conflict is
# left untouched.
MODE_DRIFT_FILES="$(git ls-files -s -- 'scripts/**/*.sh' 2>/dev/null | awk '$1 != "100755" && $3 == "0" { print $NF }')"
if [ -n "$MODE_DRIFT_FILES" ]; then
  echo ""
  echo "Restoring the executable bit on scripts that lost it during this sync:"
  while IFS= read -r f; do
    echo "  $f"
    git update-index --chmod=+x "$f"
  done <<<"$MODE_DRIFT_FILES"
fi

# A clean merge/apply says nothing about whether two migrations now share a
# parent, so check separately regardless of conflict status. `-f` + explicit
# `bash` invocation, not `-x` + direct execution: a missing executable bit
# must fail loud here, not silently skip the check.
ALEMBIC_OK=1
ALEMBIC_LOG=""
if [ -f "$REPO_ROOT/scripts/mystic_auth/upstream-sync/check-alembic-heads.sh" ]; then
  if ! ALEMBIC_LOG="$(bash "$REPO_ROOT/scripts/mystic_auth/upstream-sync/check-alembic-heads.sh" 2>&1)"; then
    ALEMBIC_OK=0
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
  if [ "$ALEMBIC_OK" -eq 0 ]; then
    echo ""
    echo "Also, once the above is resolved, check the migration history:"
    echo "$ALEMBIC_LOG"
  fi
  exit 1
fi

if [ "$ALEMBIC_OK" -eq 0 ]; then
  echo ""
  echo "$ALEMBIC_LOG"
  echo ""
  echo "Not committing -- resolve the alembic branch above first, then:"
  echo "  git add backend/alembic/versions/<merge migration file>"
  echo "  git commit -m \"Sync upstream template updates (mystic-auth@${UPSTREAM_SHA_SHORT})\""
  echo "(${SYNC_STATE_FILE} and everything else from the sync are already staged -- nothing else to do for them.)"
  exit 1
fi

git commit -m "Sync upstream template updates (mystic-auth@${UPSTREAM_SHA_SHORT})"

cat <<EOF

Synced and committed as a single commit (mystic-auth@${UPSTREAM_SHA_SHORT}).
Your history stays yours -- no upstream commits were imported.

Before trusting this, rebuild and rerun the test suite -- a sync can change
behavior underneath you even when every file merged automatically:

  docker compose -f docker/mystic_auth/compose/docker-compose.dev.yml -f docker/app/compose/docker-compose.dev.yml --env-file env/mystic_auth/.env.dev --env-file env/app/.env.dev up -d --build
  scripts/mystic_auth/docker/dev/backend-exec.sh python -m pytest tests/backend/mystic_auth/unit tests/backend/mystic_auth/integration tests/backend/mystic_auth/security
  # frontend: see docs/mystic_auth/testing/overview.md for the equivalent commands
  # scripts/mystic_auth/docker/dev/backend-exec.sh wraps the two Windows/Git Bash and native-Linux
  # workarounds documented in
  # docs/mystic_auth/docker/dev-workflow.md#running-a-one-off-command-inside-a-container
  # -- safe to use on every platform.
EOF
