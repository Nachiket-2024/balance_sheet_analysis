#!/usr/bin/env bash
# Regression test for sync-upstream.sh, run against throwaway fake
# "upstream" and "consumer" repos under a temp dir -- never touches this
# repo's own history. Run manually after touching sync-upstream.sh:
#   scripts/test-sync-upstream.sh
#
# Covers the two bugs a naive `git merge --squash` sync has, and that this
# script's incremental-diff design was built specifically to fix:
#   - stale "incoming commits" preview after the first sync
#   - phantom conflicts on files nobody touched, once there's no merge-base
# plus the actual conflict path, the squash-history-never-imported property,
# and upgrading an existing repo that predates the state-file mechanism.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REAL_SCRIPT="$REPO_ROOT/scripts/sync-upstream.sh"
BASE="$(mktemp -d)"
trap 'rm -rf "$BASE"' EXIT
cd "$BASE"

# sync-upstream.sh finds its repo root via its OWN file location, not the
# caller's cwd (so it works from anywhere in a real repo) -- so testing it
# against a fake repo means giving that fake repo its own copy of the
# script, at the same relative path a real consumer repo would have it.
install_script() {
  mkdir -p "$1/scripts"
  cp "$REAL_SCRIPT" "$1/scripts/sync-upstream.sh"
  chmod +x "$1/scripts/sync-upstream.sh"
}

pass() { echo "PASS: $1"; }
fail() { echo "FAIL: $1"; exit 1; }

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
yes | ./scripts/sync-upstream.sh "$BASE/upstream" >/dev/null 2>&1 || true

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
yes | ./scripts/sync-upstream.sh "$BASE/upstream" >/dev/null 2>&1 || true

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
yes | ./scripts/sync-upstream.sh "$BASE/upstream" >/dev/null 2>&1
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
yes | ./scripts/sync-upstream.sh "$BASE/upstream" >/dev/null 2>&1 || true
[ -f .mystic-auth-sync-state ] || fail "transition: state file not created on upgrade"
pass "transition: old-script user with no state file falls back to squash path safely"

echo ""
echo "=== ALL CHECKS PASSED ==="
