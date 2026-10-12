#!/usr/bin/env bash
# Regression test for sync-upstream.sh, run against throwaway fake
# "upstream" and "consumer" repos under a temp dir. Never touches this
# repo's own history. Run manually after touching sync-upstream.sh:
#   tests/scripts/mystic_auth/upstream-sync/test-sync-upstream.sh
#
# Covers the two bugs a naive `git merge --squash` sync has, which the
# incremental-diff design fixes:
#   - stale "incoming commits" preview after the first sync
#   - phantom conflicts on files nobody touched, once there's no merge-base
# plus the real conflict path, the squash-history-never-imported property,
# and upgrading an existing repo that predates the state-file mechanism.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
REAL_SCRIPT="$REPO_ROOT/scripts/mystic_auth/upstream-sync/sync-upstream.sh"
BASE="$(mktemp -d)"
trap 'rm -rf "$BASE"' EXIT
cd "$BASE"

# sync-upstream.sh finds its repo root via its own file location, not the
# caller's cwd, so a fake repo needs its own copy at the same relative path
# (scripts/mystic_auth/upstream-sync/). check-alembic-heads.sh comes along too, since
# sync-upstream.sh looks for it next to itself.
REAL_ALEMBIC_SCRIPT="$REPO_ROOT/scripts/mystic_auth/upstream-sync/check-alembic-heads.sh"
install_script() {
  mkdir -p "$1/scripts/mystic_auth/upstream-sync"
  cp "$REAL_SCRIPT" "$1/scripts/mystic_auth/upstream-sync/sync-upstream.sh"
  cp "$REAL_ALEMBIC_SCRIPT" "$1/scripts/mystic_auth/upstream-sync/check-alembic-heads.sh"
  chmod +x "$1/scripts/mystic_auth/upstream-sync/sync-upstream.sh" "$1/scripts/mystic_auth/upstream-sync/check-alembic-heads.sh"
}

# A minimal but structurally real alembic migration file -- just enough for
# check-alembic-heads.sh's static parsing (revision/down_revision lines) to
# treat it like a genuine migration.
make_migration() {
  local dir="$1" revision="$2" down_revision="$3" message="$4"
  mkdir -p "$dir"
  cat > "$dir/${revision}_${message// /_}.py" <<EOF
"""${message}

Revision ID: ${revision}
Revises: ${down_revision}

"""
revision: str = '${revision}'
down_revision: str | None = $( [ "$down_revision" = "None" ] && echo "None" || echo "'${down_revision}'" )
EOF
}

pass() { echo "PASS: $1"; }
fail() { echo "FAIL: $1"; exit 1; }

echo "=== Executable bit: every tracked shell script must be tracked as 755 in THIS repo's git index ==="
# Checked against the git index, not the working tree: core.filemode=false
# (common on Windows) never flags a local `chmod +x` as a diff, so a script
# can run fine locally while staying non-executable for every other clone.
# The scenarios below all `chmod +x` their fake-repo copies explicitly, so
# none of them would catch this -- only checking this repo's own tracked
# mode does.
NON_EXEC_SH="$(cd "$REPO_ROOT" && git ls-files -s -- '*.sh' | awk '$1 != "100755" { print }')"
if [ -n "$NON_EXEC_SH" ]; then
  fail "executable bit: found tracked shell scripts without mode 755:
$NON_EXEC_SH"
fi
pass "executable bit: every tracked shell script is mode 755"

echo "=== Setting up fake upstream ==="
mkdir upstream && cd upstream
git init -q -b main
git config user.email up@test.com; git config user.name Upstream
mkdir -p mystic_auth app
echo "core v1" > mystic_auth/core.py
cat > app/main.py <<'EOF'
app.include_router(health_router)
app.include_router(auth_router)
EOF
echo "# readme" > README.md
git add -A && git commit -q -m "upstream commit 1"
cd "$BASE"

echo "=== Simulating 'Use this template' (fresh history, no shared ancestry) ==="
mkdir consumer && cd consumer
git init -q -b main
git config user.email me@test.com; git config user.name Consumer
cp -r ../upstream/mystic_auth .
cp -r ../upstream/app .
cp ../upstream/README.md .
mkdir -p backend/app
echo "downstream-only app code" > backend/app/local_only.py
git add -A && git commit -q -m "Initial commit from template"
install_script "$BASE/consumer"
git add -A && git commit -q -m "Add sync script (part of template)"

echo "=== Sync refuses to mix staged downstream work into its commit ==="
echo "downstream staged work" > staged-downstream.txt
git add staged-downstream.txt
set +e
./scripts/mystic_auth/upstream-sync/sync-upstream.sh "$BASE/upstream" >/tmp/dirty-index-sync.log 2>&1
DIRTY_INDEX_EXIT=$?
set -e
[ "$DIRTY_INDEX_EXIT" -ne 0 ] || fail "dirty index: sync should refuse staged work"
grep -q "Git index contains staged changes" /tmp/dirty-index-sync.log || fail "dirty index: refusal was not actionable"
pass "dirty index: sync refuses staged downstream work"
git restore --staged staged-downstream.txt
rm -f staged-downstream.txt /tmp/dirty-index-sync.log

echo "ignored-secret.env" > .gitignore
git add .gitignore && git commit -q -m "Ignore local secret fixture"
echo "local secret fixture" > ignored-secret.env

echo ""
echo "=== SYNC 1 (first ever, no state file -> squash path; tree already == upstream) ==="
echo "downstream-only app code that is not committed yet" > backend/app/uncommitted_only.py
rm mystic_auth/core.py
yes | ./scripts/mystic_auth/upstream-sync/sync-upstream.sh "$BASE/upstream" >/dev/null 2>&1 || true

[ -f .mystic-auth-sync-state ] || fail "sync 1: state file not created"
pass "sync 1: state file created"
[ -f backend/app/local_only.py ] || fail "sync 1: downstream-only app path was lost"
pass "sync 1: downstream-only app path was preserved"
[ -f backend/app/uncommitted_only.py ] || fail "sync 1: unstaged downstream app path was lost"
pass "sync 1: unstaged downstream app path was restored"
[ ! -e mystic_auth/core.py ] || fail "sync 1: unstaged downstream deletion was overwritten"
pass "sync 1: unstaged downstream deletion was restored"
[ -f ignored-secret.env ] || fail "sync 1: ignored downstream file was lost"
pass "sync 1: ignored downstream file was preserved"
# Put the fixture back into its normal post-sync shape before exercising the
# later incremental-sync scenarios.
git restore mystic_auth/core.py
git rm -q mystic_auth/core.py
git commit -q -m "Move an upstream file into the app split"
git log --oneline | grep -qi "upstream commit 1" && fail "sync 1: upstream commit message leaked into consumer history" || pass "sync 1: no upstream commit text in consumer log"

echo "=== Consumer makes their own edits (after their first sync, like a real user would) ==="
cat >> app/main.py <<'EOF'
app.include_router(my_projects_router)  # mine
EOF
echo "my sdk exports" > app/app_sdk.py
git add -A && git commit -q -m "Add my own feature"

echo ""
echo "=== Upstream ships release 2: unrelated file change + new file + new line in shared file ==="
cd "$BASE/upstream"
echo "core v2" > mystic_auth/core.py
echo "new_feature = True" > mystic_auth/new_feature.py
echo "remove me in the next release" > mystic_auth/obsolete.py
cat > app/main.py <<'EOF'
app.include_router(health_router)
app.include_router(billing_router)  # upstream's, inserted in the middle
app.include_router(auth_router)
EOF
git add -A && git commit -q -m "upstream commit 2: core v2, new_feature.py, billing router"
cd "$BASE/consumer"

echo ""
echo "=== Checking preview only shows NEW commits (regression test for stale-preview bug) ==="
git fetch "$BASE/upstream" main -q
PREVIEW="$(git log "$(cat .mystic-auth-sync-state)..FETCH_HEAD" --oneline)"
echo "$PREVIEW" | grep -q "upstream commit 2" || fail "preview: missing new commit"
echo "$PREVIEW" | grep -q "upstream commit 1" && fail "preview: stale commit 1 reappeared" || pass "preview: shows only new commits since last sync"

echo ""
echo "=== SYNC 2 (incremental diff/apply path) ==="
echo "downstream-only app code added before an incremental sync" > backend/app/uncommitted_incremental.py
yes | ./scripts/mystic_auth/upstream-sync/sync-upstream.sh "$BASE/upstream" >/tmp/sync2.log 2>&1 || true

[ -f mystic_auth/core.py ] || { cat /tmp/sync2.log; fail "sync 2: missing upstream baseline path was not restored"; }
[ "$(cat mystic_auth/core.py)" = "core v2" ] || fail "sync 2: untouched upstream file didn't update"
pass "sync 2: unrelated upstream-owned file updated cleanly"
[ -f mystic_auth/core.py ] || fail "sync 2: missing upstream baseline path was not restored"
pass "sync 2: missing upstream baseline path was restored before apply"
[ -f mystic_auth/new_feature.py ] || fail "sync 2: new upstream file missing"
pass "sync 2: new upstream file added"
[ -f mystic_auth/obsolete.py ] || fail "sync 2: fixture for later upstream deletion missing"
pass "sync 2: later-deleted upstream file added"
grep -q "billing_router" app/main.py || fail "sync 2: upstream's new router line missing"
grep -q "my_projects_router" app/main.py || fail "sync 2: consumer's router line lost on second sync"
grep -q "<<<<<<<" app/main.py && fail "sync 2: got a phantom conflict on a non-overlapping edit" || pass "sync 2: shared file auto-merged both sides cleanly, no phantom conflict"
[ "$(cat app/app_sdk.py)" = "my sdk exports" ] || fail "sync 2: consumer file clobbered"
pass "sync 2: consumer-only file still untouched"
[ -f backend/app/uncommitted_incremental.py ] || fail "sync 2: unstaged downstream app path was lost"
pass "sync 2: unstaged downstream app path was restored"
rm -f /tmp/sync2.log

echo ""
echo "=== Upstream ships release 3: inserts a line at the SAME spot consumer appended theirs -> real conflict ==="
cd "$BASE/upstream"
cat > app/main.py <<'EOF'
app.include_router(health_router)
app.include_router(billing_router)  # upstream's, inserted in the middle
app.include_router(auth_router)
app.include_router(admin_router)    # upstream's, appended at the same spot consumer appended theirs
EOF
rm mystic_auth/obsolete.py
git add -A && git commit -q -m "upstream commit 3: admin router appended right where consumer also appended"
cd "$BASE/consumer"

echo ""
echo "=== SYNC 3 (expect a real conflict) ==="
set +e
yes | ./scripts/mystic_auth/upstream-sync/sync-upstream.sh "$BASE/upstream" >/tmp/sync3.log 2>&1
SYNC3_EXIT=$?
set -e
[ "$SYNC3_EXIT" -ne 0 ] || fail "sync 3: expected non-zero exit on conflict"
pass "sync 3: script exits non-zero on conflict"
grep -q "DELETE mystic_auth/obsolete.py" /tmp/sync3.log || fail "sync 3: upstream deletion was not shown before confirmation"
pass "sync 3: upstream deletion shown explicitly before confirmation"
grep -q "<<<<<<<" app/main.py || fail "sync 3: no conflict markers found"
pass "sync 3: conflict markers present for genuine same-line collision"
git diff --cached --name-only | grep -q ".mystic-auth-sync-state" || fail "sync 3: state file not staged despite conflict"
pass "sync 3: sync-state file still staged even though content conflicted"

echo ""
echo "=== Resolve conflict manually, commit, verify history stays clean ==="
cat > app/main.py <<'EOF'
app.include_router(health_router)
app.include_router(billing_router)
app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(my_projects_router)  # mine, kept
EOF
git add app/main.py
git commit -q -m "Sync upstream template updates (resolved conflict)"
[ ! -e mystic_auth/obsolete.py ] || fail "final: upstream-deleted file was retained"
pass "final: upstream-deleted file removed from mystic_auth"

# Deliberately NOT --all: refs/remotes/upstream/* legitimately contains
# upstream's commits (that's just the fetched remote-tracking branch) --
# the property under test is that the CURRENT BRANCH's own history doesn't.
git log --oneline | grep -qi "upstream commit" && fail "final: upstream commit messages leaked into consumer history" || pass "final: consumer git log never contains upstream's commit history"
git merge-base --is-ancestor "$(cd "$BASE/upstream" && git rev-parse HEAD)" HEAD 2>/dev/null && fail "final: upstream HEAD became an ancestor of consumer branch" || pass "final: upstream commits never became ancestors (squash property preserved)"

echo ""
echo "=== Transition scenario: old-script user (prior sync commit, but no state file) ==="
cd "$BASE"
mkdir old-consumer && cd old-consumer
git init -q -b main
git config user.email old@test.com; git config user.name OldConsumer
cp -r "$BASE/upstream/mystic_auth" .
cp -r "$BASE/upstream/app" .
cp "$BASE/upstream/README.md" .
git add -A && git commit -q -m "Initial commit from template"
install_script "$BASE/old-consumer"
git add -A && git commit -q -m "Sync upstream template updates (mystic-auth@oldsha)" --allow-empty
yes | ./scripts/mystic_auth/upstream-sync/sync-upstream.sh "$BASE/upstream" >/dev/null 2>&1 || true
[ -f .mystic-auth-sync-state ] || fail "transition: state file not created on upgrade"
pass "transition: old-script user with no state file falls back to squash path safely"

echo ""
echo "=== rerere: confirm sync-upstream.sh turns it on for the consumer repo ==="
cd "$BASE/consumer"
[ "$(git config --get rerere.enabled)" = "true" ] || fail "rerere: not enabled after running sync-upstream.sh"
pass "rerere: enabled by sync-upstream.sh"

echo ""
echo "=== Silent partial-apply guard: git-apply-succeeds-but-nothing-changed should be caught, not committed ==="
cd "$BASE"
mkdir shim-upstream && cd shim-upstream
git init -q -b main
git config user.email up@test.com; git config user.name Upstream
mkdir -p mystic_auth app
echo "core v1" > mystic_auth/core.py
echo "app v1" > app/main.py
git add -A && git commit -q -m "shim upstream base"
cd "$BASE"
mkdir shim-consumer && cd shim-consumer
git init -q -b main
git config user.email me@test.com; git config user.name Consumer
cp -r "$BASE/shim-upstream/mystic_auth" .
cp -r "$BASE/shim-upstream/app" .
git add -A && git commit -q -m "Initial commit from template"
install_script "$BASE/shim-consumer"
git add -A && git commit -q -m "Add sync script"
yes | ./scripts/mystic_auth/upstream-sync/sync-upstream.sh "$BASE/shim-upstream" >/dev/null 2>&1 || true
BASELINE_COMMIT="$(git rev-parse HEAD)"

cd "$BASE/shim-upstream"
echo "core v2 -- upstream really did change this file" > mystic_auth/core.py
git add -A && git commit -q -m "shim upstream release 2"
cd "$BASE/shim-consumer"

# Fake `git` ahead of the real one on PATH: passes every subcommand through
# except `apply`, which reports success without touching anything --
# simulating a clean-looking apply that silently dropped a file (in the
# real world, usually a binary one).
REAL_GIT="$(command -v git)"
mkdir -p "$BASE/fake-bin"
cat > "$BASE/fake-bin/git" <<EOF
#!/usr/bin/env bash
if [ "\$1" = "apply" ]; then
  echo "Applied patch to 'mystic_auth/core.py' cleanly."
  exit 0
fi
exec "$REAL_GIT" "\$@"
EOF
chmod +x "$BASE/fake-bin/git"

set +e
yes | env PATH="$BASE/fake-bin:$PATH" ./scripts/mystic_auth/upstream-sync/sync-upstream.sh "$BASE/shim-upstream" >/tmp/shim-sync.log 2>&1
SHIM_EXIT=$?
set -e

grep -q "silent partial apply" /tmp/shim-sync.log || fail "silent-apply guard: didn't detect the fake no-op apply"
pass "silent-apply guard: detected the reported-success-but-nothing-changed case"
[ "$SHIM_EXIT" -ne 0 ] || fail "silent-apply guard: script should have exited non-zero"
pass "silent-apply guard: script exits non-zero"
[ "$(git rev-parse HEAD)" = "$BASELINE_COMMIT" ] || fail "silent-apply guard: a commit landed despite the guard firing"
pass "silent-apply guard: no bogus commit landed"
[ "$(cat mystic_auth/core.py)" = "core v1" ] || fail "silent-apply guard: working tree shouldn't have moved"
pass "silent-apply guard: working tree untouched"

echo "=== Worktree-restore failure: keep the sync commit and retained stash ==="
mkdir -p backend/app
echo "downstream work awaiting restoration" > backend/app/restore_pending.py
RESTORE_BASELINE="$(git rev-parse HEAD)"
mkdir -p "$BASE/restore-fake-bin"
cat > "$BASE/restore-fake-bin/git" <<EOF
#!/usr/bin/env bash
if [ "\$1" = "stash" ] && [ "\$2" = "pop" ]; then
  echo "simulated stash restore failure" >&2
  exit 1
fi
exec "$REAL_GIT" "\$@"
EOF
chmod +x "$BASE/restore-fake-bin/git"
set +e
yes | env PATH="$BASE/restore-fake-bin:$PATH" ./scripts/mystic_auth/upstream-sync/sync-upstream.sh "$BASE/shim-upstream" >/tmp/restore-sync.log 2>&1
RESTORE_EXIT=${PIPESTATUS[1]}
set -e
[ "$RESTORE_EXIT" -ne 0 ] || fail "worktree restore: sync hid the restore failure"
grep -q "saved downstream work could not be restored cleanly" /tmp/restore-sync.log || fail "worktree restore: failure was not actionable"
pass "worktree restore: sync returned non-zero with actionable recovery"
[ "$(git rev-parse HEAD)" != "$RESTORE_BASELINE" ] || fail "worktree restore: successful sync commit was lost"
pass "worktree restore: sync commit was retained"
[ -n "$(git stash list)" ] || fail "worktree restore: failed restore did not retain the stash"
pass "worktree restore: failed restore retained the stash"
git stash drop >/dev/null
rm -f /tmp/restore-sync.log

echo ""
echo "=== Alembic branch-detection: template and app both add a migration on the same fork point ==="
cd "$BASE"
mkdir alembic-upstream && cd alembic-upstream
git init -q -b main
git config user.email up@test.com; git config user.name Upstream
make_migration backend/alembic/versions aaa000000001 None "init"
git add -A && git commit -q -m "upstream: init migration"
cd "$BASE"
mkdir alembic-consumer && cd alembic-consumer
git init -q -b main
git config user.email me@test.com; git config user.name Consumer
cp -r "$BASE/alembic-upstream/backend" .
git add -A && git commit -q -m "Initial commit from template"
install_script "$BASE/alembic-consumer"
git add -A && git commit -q -m "Add sync script"
yes | ./scripts/mystic_auth/upstream-sync/sync-upstream.sh "$BASE/alembic-upstream" >/dev/null 2>&1 || true

# Consumer adds their own migration on top of the current (single) head.
make_migration backend/alembic/versions bbb000000002 aaa000000001 "add my table"
git add -A && git commit -q -m "my own migration"

# Upstream, independently, also ships a migration on top of that same head --
# the two-heads scenario nothing in a naive sync flow would catch.
cd "$BASE/alembic-upstream"
make_migration backend/alembic/versions ccc000000003 aaa000000001 "upstream migration"
git add -A && git commit -q -m "upstream: another migration on the same head"
cd "$BASE/alembic-consumer"

set +e
yes | ./scripts/mystic_auth/upstream-sync/sync-upstream.sh "$BASE/alembic-upstream" >/tmp/alembic-sync.log 2>&1
ALEMBIC_SYNC_EXIT=$?
set -e

grep -q "multiple alembic heads" /tmp/alembic-sync.log || fail "alembic-heads: sync didn't report the branched migration history"
pass "alembic-heads: sync reports the branched migration history"
[ "$ALEMBIC_SYNC_EXIT" -ne 0 ] || fail "alembic-heads: sync should have exited non-zero instead of auto-committing"
pass "alembic-heads: sync exits non-zero instead of auto-committing"
git log --oneline -1 | grep -q "my own migration" || fail "alembic-heads: sync committed on top of the branch without a merge migration"
pass "alembic-heads: no auto-commit landed on top of the unresolved branch"
git diff --cached --name-only | grep -q ".mystic-auth-sync-state" || fail "alembic-heads: state file not staged despite blocking the commit"
pass "alembic-heads: state file still staged so a manual commit after the fix needs no extra step"

echo ""
echo "=== Executable-bit self-heal: a scripts/**/*.sh landing non-executable after a sync should get auto-fixed ==="
cd "$BASE"
mkdir mode-upstream && cd mode-upstream
git init -q -b main
git config user.email up@test.com; git config user.name Upstream
mkdir -p mystic_auth app
echo "core v1" > mystic_auth/core.py
git add -A && git commit -q -m "mode-upstream base"
cd "$BASE"
mkdir mode-consumer && cd mode-consumer
git init -q -b main
git config user.email me@test.com; git config user.name Consumer
cp -r "$BASE/mode-upstream/mystic_auth" .
cp -r "$BASE/mode-upstream/app" .
git add -A && git commit -q -m "Initial commit from template"
install_script "$BASE/mode-consumer"
git add -A && git commit -q -m "Add sync script"
yes | ./scripts/mystic_auth/upstream-sync/sync-upstream.sh "$BASE/mode-upstream" >/dev/null 2>&1 || true

# Upstream ships a new script committed non-executable (someone forgot
# `chmod +x`) -- a stand-in for whatever mechanism causes the drift
# downstream; the self-heal step doesn't care which one it was.
cd "$BASE/mode-upstream"
mkdir -p scripts/docker
printf '#!/usr/bin/env bash\necho hi\n' > scripts/docker/new-helper.sh
git add -A
git update-index --chmod=-x scripts/docker/new-helper.sh
git commit -q -m "upstream: add new-helper.sh (accidentally non-executable)"
git ls-files -s scripts/docker/new-helper.sh | grep -q '^100644' || fail "mode self-heal: test setup didn't actually commit the fixture as non-executable"
cd "$BASE/mode-consumer"

yes | ./scripts/mystic_auth/upstream-sync/sync-upstream.sh "$BASE/mode-upstream" >/dev/null 2>&1 || true

git ls-files -s -- 'scripts/**/*.sh' | awk '$1 != "100755" { print; found=1 } END { exit found }' \
  || fail "mode self-heal: a scripts/**/*.sh file is still tracked non-executable after the sync ran"
pass "mode self-heal: sync-upstream.sh restored the executable bit on the newly-synced script"

echo ""
echo "=== Relocated-file guard: upstream moving a file the consumer customized should give actionable guidance, not a raw git-apply dump ==="
cd "$BASE"
mkdir move-upstream && cd move-upstream
git init -q -b main
git config user.email up@test.com; git config user.name Upstream
mkdir -p mystic_auth app old-location
echo "core v1" > mystic_auth/core.py
echo "compose v1" > old-location/compose.yml
git add -A && git commit -q -m "move-upstream base"
cd "$BASE"
mkdir move-consumer && cd move-consumer
git init -q -b main
git config user.email me@test.com; git config user.name Consumer
cp -r "$BASE/move-upstream/mystic_auth" .
cp -r "$BASE/move-upstream/app" .
cp -r "$BASE/move-upstream/old-location" .
git add -A && git commit -q -m "Initial commit from template"
install_script "$BASE/move-consumer"
git add -A && git commit -q -m "Add sync script"
yes | ./scripts/mystic_auth/upstream-sync/sync-upstream.sh "$BASE/move-upstream" >/dev/null 2>&1 || true

# Consumer customizes the file at its old path...
echo "compose v1 -- my own tweak" > old-location/compose.yml
git add -A && git commit -q -m "my own customization of compose.yml"

# ...while upstream, independently, relocates that same file to a new
# directory (delete old-location/compose.yml, add new-location/compose.yml).
# Neither side has matching content to 3-way-merge the delete hunk against,
# so `git apply --3way` hard-fails outright instead of leaving conflict
# markers -- the case this guard is for.
cd "$BASE/move-upstream"
git rm -q old-location/compose.yml
mkdir -p new-location
echo "compose v2 -- restructured" > new-location/compose.yml
git add -A && git commit -q -m "upstream: move compose.yml to new-location/"
cd "$BASE/move-consumer"

set +e
yes | ./scripts/mystic_auth/upstream-sync/sync-upstream.sh "$BASE/move-upstream" >/tmp/move-sync.log 2>&1
MOVE_SYNC_EXIT=$?
set -e

grep -q "moved or deleted" /tmp/move-sync.log || fail "relocated-file guard: didn't detect the hard-failed apply on the moved file"
pass "relocated-file guard: detected the hard-failed apply on the moved file"
grep -q "old-location/compose.yml" /tmp/move-sync.log || fail "relocated-file guard: didn't name the specific path that failed"
pass "relocated-file guard: names the specific path that failed"
grep -q -- "--3way --index -" /tmp/move-sync.log || fail "relocated-file guard: didn't suggest the re-diff-and-exclude recipe"
pass "relocated-file guard: suggests the re-diff-and-exclude recipe"
[ "$MOVE_SYNC_EXIT" -ne 0 ] || fail "relocated-file guard: sync should have exited non-zero"
pass "relocated-file guard: sync exits non-zero"
[ -z "$(git diff --cached --name-only)" ] || fail "relocated-file guard: something got staged despite the hard failure"
pass "relocated-file guard: nothing staged/committed despite the hard failure"

echo "=== Upstream-owned script renames: apply even when the old path is already absent ==="
cd "$BASE"
mkdir script-rename-upstream && cd script-rename-upstream
git init -q -b main
git config user.email up@test.com; git config user.name Upstream
mkdir -p scripts/mystic_auth/db scripts/mystic_auth/testing
printf '#!/usr/bin/env bash\necho backup\n' > scripts/mystic_auth/db/backup_failure_alert.sh
printf '#!/usr/bin/env bash\necho restore\n' > scripts/mystic_auth/db/db_restore.sh
printf '#!/usr/bin/env bash\necho seed\n' > scripts/mystic_auth/testing/seed-codex-accessibility-user.sh
chmod +x scripts/mystic_auth/db/*.sh scripts/mystic_auth/testing/*.sh
git add -A && git commit -q -m "script-rename-upstream base"
cd "$BASE"
mkdir script-rename-consumer && cd script-rename-consumer
git init -q -b main
git config user.email me@test.com; git config user.name Consumer
cp -r "$BASE/script-rename-upstream/scripts" .
git add -A && git commit -q -m "Initial commit from template"
install_script "$BASE/script-rename-consumer"
git add -A && git commit -q -m "Add sync script"
yes | ./scripts/mystic_auth/upstream-sync/sync-upstream.sh "$BASE/script-rename-upstream" >/dev/null 2>&1 || true

# The consumer removed the old source path independently before the upstream
# rename arrived. This is the exact case that made git apply require a path
# that no longer existed in the index.
git rm -q scripts/mystic_auth/db/backup_failure_alert.sh
git commit -q -m "Consumer removes obsolete backup helper"
cd "$BASE/script-rename-upstream"
git mv scripts/mystic_auth/db/backup_failure_alert.sh scripts/mystic_auth/db/database-backup-failure-alert.sh
mkdir -p scripts/mystic_auth/db/database-backup scripts/mystic_auth/db/database-restore tests/scripts/mystic_auth/accessibility
git mv scripts/mystic_auth/db/database-backup-failure-alert.sh scripts/mystic_auth/db/database-backup/database-backup-failure-alert.sh
git mv scripts/mystic_auth/db/db_restore.sh scripts/mystic_auth/db/database-restore/database-restore.sh
git mv scripts/mystic_auth/testing/seed-codex-accessibility-user.sh tests/scripts/mystic_auth/accessibility/seed-accessibility-user.sh
git add -A && git commit -q -m "upstream: reorganize maintenance scripts"
cd "$BASE/script-rename-consumer"

printf 'y\n' | ./scripts/mystic_auth/upstream-sync/sync-upstream.sh "$BASE/script-rename-upstream" >/tmp/script-rename-sync.log 2>&1 \
  || fail "script rename: sync failed when an old source path was absent"
[ -f scripts/mystic_auth/db/database-backup/database-backup-failure-alert.sh ] || fail "script rename: backup target missing"
[ -f scripts/mystic_auth/db/database-restore/database-restore.sh ] || fail "script rename: restore target missing"
[ -f tests/scripts/mystic_auth/accessibility/seed-accessibility-user.sh ] || fail "script rename: seed target missing"
[ ! -e scripts/mystic_auth/db/backup_failure_alert.sh ] || fail "script rename: old backup path retained"
[ ! -e scripts/mystic_auth/db/db_restore.sh ] || fail "script rename: old restore path retained"
[ -f .mystic-auth-sync-state ] || fail "script rename: sync state was not updated"
git log -1 --format=%s | grep -q "Sync upstream template updates" \
  || fail "script rename: sync did not create its commit"
pass "script rename: upstream-owned renames applied and committed"

echo "=== Ownership guard: upstream touching a fork-owned path must block the sync ==="
cd "$BASE"
mkdir own-upstream && cd own-upstream
git init -q -b main
git config user.email up@test.com; git config user.name Upstream
mkdir -p mystic_auth backend/app frontend/src/app tests/backend/app ci/mystic_auth docs/app
echo "core v1" > mystic_auth/core.py
echo "main v1" > backend/app/main.py
echo "sdk v1" > backend/app/sdk.py
echo "App v1" > frontend/src/app/App.tsx
echo "sdk v1" > frontend/src/app/sdk.ts
printf '// template bootstrap comment v1\n// stable context 1\n// stable context 2\n// stable context 3\n// stable context 4\n// stable context 5\nconst appValue = 1;\n' > frontend/src/app/main.tsx
printf '// template theme comment v1\n// stable context 1\n// stable context 2\n// stable context 3\n// stable context 4\n// stable context 5\nconst themeValue = 1;\n' > frontend/src/app/theme.ts
echo "downstream test v1" > tests/backend/app/test_downstream.py
echo "template CI v1" > ci/mystic_auth/backend.sh
echo "readme v1" > docs/app/README.md
echo "root readme v1" > README.md
git add -A && git commit -q -m "own-upstream base"
cd "$BASE"
mkdir own-consumer && cd own-consumer
git init -q -b main
git config user.email me@test.com; git config user.name Consumer
cp -r "$BASE/own-upstream/mystic_auth" .
cp -r "$BASE/own-upstream/backend" .
cp -r "$BASE/own-upstream/frontend" .
cp -r "$BASE/own-upstream/tests" .
cp -r "$BASE/own-upstream/ci" .
cp -r "$BASE/own-upstream/docs" .
cp "$BASE/own-upstream/README.md" .
git add -A && git commit -q -m "Initial commit from template"
install_script "$BASE/own-consumer"
git add -A && git commit -q -m "Add sync script"
yes | ./scripts/mystic_auth/upstream-sync/sync-upstream.sh "$BASE/own-upstream" >/dev/null 2>&1 || true

# Projects created before the CI split receive the three app entrypoints once.
cd "$BASE/own-upstream"
mkdir -p ci/app
echo "app backend CI v1" > ci/app/backend.sh
echo "app frontend CI v1" > ci/app/frontend.sh
echo "app browser CI v1" > ci/app/frontend-e2e.sh
git add -A && git commit -q -m "upstream: introduce split app CI entrypoints"
cd "$BASE/own-consumer"
yes | ./scripts/mystic_auth/upstream-sync/sync-upstream.sh "$BASE/own-upstream" >/dev/null 2>&1 || true
[ -f ci/app/backend.sh ] || fail "ownership bootstrap: app backend CI entrypoint was not adopted"
[ -f ci/app/frontend.sh ] || fail "ownership bootstrap: app frontend CI entrypoint was not adopted"
[ -f ci/app/frontend-e2e.sh ] || fail "ownership bootstrap: app browser CI entrypoint was not adopted"
pass "ownership bootstrap: pre-split consumer adopted the three app CI entrypoints"
echo "downstream app CI" > ci/app/custom_checks.sh

# Upstream, after that first sync, commits to a fork-owned path it should
# never touch again (backend/app/custom_route.py, not one of the extend-in-
# place exceptions) alongside an innocuous template-owned change.
cd "$BASE/own-upstream"
echo "owned by the fork, upstream must not add this" > backend/app/custom_route.py
echo "upstream must not add this" > tests/backend/app/test_upstream_accident.py
echo "upstream must not add this" > ci/app/upstream_accident.sh
echo "template reference test update" >> tests/backend/app/test_downstream.py
echo "core v2" > mystic_auth/core.py
echo "root readme v2 -- upstream must not touch this" > README.md
git add -A && git commit -q -m "upstream: accidentally ships into backend/app/"
cd "$BASE/own-consumer"

set +e
yes | ./scripts/mystic_auth/upstream-sync/sync-upstream.sh "$BASE/own-upstream" >/tmp/own-sync.log 2>&1
OWN_SYNC_EXIT=${PIPESTATUS[1]}
set -e

grep -q "downstream-owned paths" /tmp/own-sync.log || fail "ownership guard: didn't report the violation"
pass "ownership guard: reports the violation"
grep -q "backend/app/custom_route.py" /tmp/own-sync.log || fail "ownership guard: didn't name the offending path"
pass "ownership guard: names the offending path"
grep -q "tests/backend/app/test_upstream_accident.py" /tmp/own-sync.log || fail "ownership guard: didn't name the downstream test path"
pass "ownership guard: names downstream test paths"
grep -q "ci/app/upstream_accident.sh" /tmp/own-sync.log || fail "ownership guard: didn't name the downstream CI path"
pass "ownership guard: names downstream CI paths"
[ "$OWN_SYNC_EXIT" -ne 0 ] || fail "ownership guard: sync should have exited non-zero"
pass "ownership guard: sync exits non-zero"
[ -z "$(git diff --cached --name-only)" ] || fail "ownership guard: something got staged despite the violation"
pass "ownership guard: nothing staged despite the violation"
[ "$(cat mystic_auth/core.py)" = "core v1" ] || fail "ownership guard: template-owned file changed despite the blocked sync"
pass "ownership guard: template-owned change also withheld until the violation is resolved"

echo "=== Ownership guard: extend-in-place exceptions must NOT be blocked ==="
cd "$BASE/own-upstream"
git rm -q backend/app/custom_route.py
git rm -q tests/backend/app/test_upstream_accident.py
git rm -q ci/app/upstream_accident.sh
git commit -q -m "upstream: revert the accidental backend/app/ ship"
echo "main v2 -- extended in place" > backend/app/main.py
echo "App v2 -- extended in place" > frontend/src/app/App.tsx
git add -A && git commit -q -m "upstream: legitimate edits to the shared extend-in-place files"
cd "$BASE/own-consumer"

set +e
yes | ./scripts/mystic_auth/upstream-sync/sync-upstream.sh "$BASE/own-upstream" >/tmp/own-sync-2.log 2>&1
# PIPESTATUS[1], not $?: `yes` gets SIGPIPE (141) the instant the script
# below it exits and stops reading, and with pipefail set that can win over
# the script's own (successful) exit status depending on timing -- the
# script's actual code is always the second element.
OWN_SYNC_EXIT_2=${PIPESTATUS[1]}
set -e

grep -q "downstream-owned paths" /tmp/own-sync-2.log && fail "ownership guard: flagged an extend-in-place exception as a violation"
pass "ownership guard: backend/app/main.py and frontend/src/app/App.tsx stay unblocked"
[ "$OWN_SYNC_EXIT_2" -eq 0 ] || fail "ownership guard: sync of the legitimate exception-only change should have succeeded"
pass "ownership guard: sync succeeds once the violation is gone"
[ "$(cat backend/app/main.py)" = "main v2 -- extended in place" ] || fail "ownership guard: main.py extend-in-place edit didn't land"
pass "ownership guard: extend-in-place edit lands normally"
[ "$(cat README.md)" = "root readme v1" ] || fail "ownership guard: upstream README change overwrote the downstream copy"
pass "ownership guard: upstream README change was ignored and downstream copy preserved"
grep -q "template reference test update" tests/backend/app/test_downstream.py \
  || fail "ownership guard: inherited reference test update did not land"
pass "ownership guard: inherited reference test update lands normally"

echo "=== Ownership guard: allow comment-only app-shell maintenance, keep code protected ==="
cd "$BASE/own-consumer"
sed -i 's/const appValue = 1;/const downstreamAppValue = 2;/' frontend/src/app/main.tsx
sed -i 's/const themeValue = 1;/const downstreamThemeValue = 2;/' frontend/src/app/theme.ts
git add -A && git commit -q -m "consumer: customize app shell"
cd "$BASE/own-upstream"
sed -i 's/template bootstrap comment v1/template bootstrap comment v2/' frontend/src/app/main.tsx
sed -i 's/template theme comment v1/template theme comment v2/' frontend/src/app/theme.ts
git add -A && git commit -q -m "upstream: refresh app-shell comments"
cd "$BASE/own-consumer"

set +e
yes | ./scripts/mystic_auth/upstream-sync/sync-upstream.sh "$BASE/own-upstream" >/tmp/own-sync-comments.log 2>&1
OWN_SYNC_COMMENTS_EXIT=${PIPESTATUS[1]}
set -e
[ "$OWN_SYNC_COMMENTS_EXIT" -eq 0 ] || fail "comment-only maintenance: sync was blocked"
grep -q 'template bootstrap comment v2' frontend/src/app/main.tsx || fail "comment-only maintenance: main.tsx comment did not update"
grep -q 'downstreamAppValue = 2' frontend/src/app/main.tsx || fail "comment-only maintenance: downstream main.tsx code was lost"
grep -q 'template theme comment v2' frontend/src/app/theme.ts || fail "comment-only maintenance: theme.ts comment did not update"
grep -q 'downstreamThemeValue = 2' frontend/src/app/theme.ts || fail "comment-only maintenance: downstream theme.ts code was lost"
pass "comment-only maintenance: comments update and downstream code remains"

cd "$BASE/own-upstream"
sed -i 's/const appValue = 1;/const upstreamAppValue = 3;/' frontend/src/app/main.tsx
echo "core v3" > mystic_auth/core.py
git add -A && git commit -q -m "upstream: attempt app-shell code change"
cd "$BASE/own-consumer"

set +e
yes | ./scripts/mystic_auth/upstream-sync/sync-upstream.sh "$BASE/own-upstream" >/tmp/own-sync-code.log 2>&1
OWN_SYNC_CODE_EXIT=${PIPESTATUS[1]}
set -e
grep -q 'downstream-owned paths' /tmp/own-sync-code.log || fail "app-shell code guard: did not report ownership violation"
[ "$OWN_SYNC_CODE_EXIT" -ne 0 ] || fail "app-shell code guard: executable-code change was not blocked"
grep -q 'frontend/src/app/main.tsx' /tmp/own-sync-code.log || fail "app-shell code guard: did not name the path"
[ "$(cat mystic_auth/core.py)" = "core v2" ] || fail "app-shell code guard: unrelated template change landed despite the violation"
pass "app-shell code guard: executable-code changes remain blocked"

echo ""
echo "=== ALL CHECKS PASSED ==="
