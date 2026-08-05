#!/usr/bin/env bash
# Regression test for sync-upstream.sh, run against throwaway fake
# "upstream" and "consumer" repos under a temp dir -- never touches this
# repo's own history. Run manually after touching sync-upstream.sh:
#   scripts/upstream-sync/test-sync-upstream.sh
#
# Covers the two bugs a naive `git merge --squash` sync has, and that this
# script's incremental-diff design was built specifically to fix:
#   - stale "incoming commits" preview after the first sync
#   - phantom conflicts on files nobody touched, once there's no merge-base
# plus the actual conflict path, the squash-history-never-imported property,
# and upgrading an existing repo that predates the state-file mechanism.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
REAL_SCRIPT="$REPO_ROOT/scripts/upstream-sync/sync-upstream.sh"
BASE="$(mktemp -d)"
trap 'rm -rf "$BASE"' EXIT
cd "$BASE"

# sync-upstream.sh finds its repo root via its own file location, not the
# caller's cwd, so a fake repo needs its own copy at the same relative path
# (scripts/upstream-sync/). check-alembic-heads.sh comes along too, since
# sync-upstream.sh looks for it next to itself.
REAL_ALEMBIC_SCRIPT="$REPO_ROOT/scripts/upstream-sync/check-alembic-heads.sh"
install_script() {
  mkdir -p "$1/scripts/upstream-sync"
  cp "$REAL_SCRIPT" "$1/scripts/upstream-sync/sync-upstream.sh"
  cp "$REAL_ALEMBIC_SCRIPT" "$1/scripts/upstream-sync/check-alembic-heads.sh"
  chmod +x "$1/scripts/upstream-sync/sync-upstream.sh" "$1/scripts/upstream-sync/check-alembic-heads.sh"
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

echo "=== Executable bit: every scripts/**/*.sh must be tracked as 755 in THIS repo's git index ==="
# Checked against the git index, not the working tree: core.filemode=false
# (common on Windows) never flags a local `chmod +x` as a diff, so a script
# can run fine locally while staying non-executable for every other clone.
# The scenarios below all `chmod +x` their fake-repo copies explicitly, so
# none of them would catch this -- only checking this repo's own tracked
# mode does.
NON_EXEC_SH="$(cd "$REPO_ROOT" && git ls-files -s -- 'scripts/**/*.sh' | awk '$1 != "100755" { print }')"
if [ -n "$NON_EXEC_SH" ]; then
  fail "executable bit: found scripts/**/*.sh tracked without mode 755:
$NON_EXEC_SH"
fi
pass "executable bit: every tracked scripts/**/*.sh is mode 755"

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
git add -A && git commit -q -m "Initial commit from template"
install_script "$BASE/consumer"
git add -A && git commit -q -m "Add sync script (part of template)"

echo ""
echo "=== SYNC 1 (first ever, no state file -> squash path; tree already == upstream) ==="
yes | ./scripts/upstream-sync/sync-upstream.sh "$BASE/upstream" >/dev/null 2>&1 || true

[ -f .mystic-auth-sync-state ] || fail "sync 1: state file not created"
pass "sync 1: state file created"
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
yes | ./scripts/upstream-sync/sync-upstream.sh "$BASE/upstream" >/dev/null 2>&1 || true

[ "$(cat mystic_auth/core.py)" = "core v2" ] || fail "sync 2: untouched upstream file didn't update"
pass "sync 2: unrelated upstream-owned file updated cleanly"
[ -f mystic_auth/new_feature.py ] || fail "sync 2: new upstream file missing"
pass "sync 2: new upstream file added"
grep -q "billing_router" app/main.py || fail "sync 2: upstream's new router line missing"
grep -q "my_projects_router" app/main.py || fail "sync 2: consumer's router line lost on second sync"
grep -q "<<<<<<<" app/main.py && fail "sync 2: got a phantom conflict on a non-overlapping edit" || pass "sync 2: shared file auto-merged both sides cleanly, no phantom conflict"
[ "$(cat app/app_sdk.py)" = "my sdk exports" ] || fail "sync 2: consumer file clobbered"
pass "sync 2: consumer-only file still untouched"

echo ""
echo "=== Upstream ships release 3: inserts a line at the SAME spot consumer appended theirs -> real conflict ==="
cd "$BASE/upstream"
cat > app/main.py <<'EOF'
app.include_router(health_router)
app.include_router(billing_router)  # upstream's, inserted in the middle
app.include_router(auth_router)
app.include_router(admin_router)    # upstream's, appended at the same spot consumer appended theirs
EOF
git add -A && git commit -q -m "upstream commit 3: admin router appended right where consumer also appended"
cd "$BASE/consumer"

echo ""
echo "=== SYNC 3 (expect a real conflict) ==="
set +e
yes | ./scripts/upstream-sync/sync-upstream.sh "$BASE/upstream" >/dev/null 2>&1
SYNC3_EXIT=$?
set -e
[ "$SYNC3_EXIT" -ne 0 ] || fail "sync 3: expected non-zero exit on conflict"
pass "sync 3: script exits non-zero on conflict"
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
git add -A && git commit -q -m "Initial commit from template"
install_script "$BASE/old-consumer"
git add -A && git commit -q -m "Sync upstream template updates (mystic-auth@oldsha)" --allow-empty
yes | ./scripts/upstream-sync/sync-upstream.sh "$BASE/upstream" >/dev/null 2>&1 || true
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
yes | ./scripts/upstream-sync/sync-upstream.sh "$BASE/shim-upstream" >/dev/null 2>&1 || true
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
mkdir -p fake-bin
cat > fake-bin/git <<EOF
#!/usr/bin/env bash
if [ "\$1" = "apply" ]; then
  echo "Applied patch to 'mystic_auth/core.py' cleanly."
  exit 0
fi
exec "$REAL_GIT" "\$@"
EOF
chmod +x fake-bin/git

set +e
yes | env PATH="$BASE/shim-consumer/fake-bin:$PATH" ./scripts/upstream-sync/sync-upstream.sh "$BASE/shim-upstream" >/tmp/shim-sync.log 2>&1
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
yes | ./scripts/upstream-sync/sync-upstream.sh "$BASE/alembic-upstream" >/dev/null 2>&1 || true

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
yes | ./scripts/upstream-sync/sync-upstream.sh "$BASE/alembic-upstream" >/tmp/alembic-sync.log 2>&1
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
yes | ./scripts/upstream-sync/sync-upstream.sh "$BASE/mode-upstream" >/dev/null 2>&1 || true

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

yes | ./scripts/upstream-sync/sync-upstream.sh "$BASE/mode-upstream" >/dev/null 2>&1 || true

git ls-files -s -- 'scripts/**/*.sh' | awk '$1 != "100755" { print; found=1 } END { exit found }' \
  || fail "mode self-heal: a scripts/**/*.sh file is still tracked non-executable after the sync ran"
pass "mode self-heal: sync-upstream.sh restored the executable bit on the newly-synced script"

echo ""
echo "=== ALL CHECKS PASSED ==="
