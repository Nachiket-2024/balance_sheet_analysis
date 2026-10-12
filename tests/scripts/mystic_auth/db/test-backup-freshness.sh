#!/usr/bin/env bash
# Deterministic regression tests for backup-freshness-check.sh.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
SCRIPT="$REPO_ROOT/scripts/mystic_auth/db/backup-verification/backup-freshness-check.sh"
TEST_DIR="$(mktemp -d)"
trap 'rm -rf "$TEST_DIR"' EXIT

pass() { echo "PASS: $1"; }
fail() { echo "FAIL: $1" >&2; exit 1; }

touch_backup() {
  local database="$1"
  local filename="$TEST_DIR/${database}-20260926-120000.dump"
  printf 'valid backup fixture\n' > "$filename"
  touch -d '5 minutes ago' "$filename"
}

echo "=== fresh non-empty backups pass ==="
touch_backup mystic_auth
touch_backup bugsink
if POSTGRES_DB=mystic_auth BACKUP_DATABASES="mystic_auth bugsink" bash "$SCRIPT" "$TEST_DIR" 1 >/dev/null; then
  pass "fresh backups are accepted"
else
  fail "fresh backups were rejected"
fi

echo "=== missing backup directory fails ==="
if POSTGRES_DB=mystic_auth BACKUP_DATABASES="mystic_auth bugsink" bash "$SCRIPT" "$TEST_DIR/missing" 1 >/dev/null 2>&1; then
  fail "missing backup directory was accepted"
else
  pass "missing backup directory is rejected"
fi

echo "=== stale backup fails ==="
touch -d '2 hours ago' "$TEST_DIR/mystic_auth-20260926-120000.dump"
if POSTGRES_DB=mystic_auth BACKUP_DATABASES=mystic_auth bash "$SCRIPT" "$TEST_DIR" 1 >/dev/null 2>&1; then
  fail "stale backup was accepted"
else
  pass "stale backup is rejected"
fi

echo "=== newest empty backup fails instead of falling back silently ==="
touch_backup mystic_auth
: > "$TEST_DIR/mystic_auth-20260926-130000.dump"
touch -d '1 minute ago' "$TEST_DIR/mystic_auth-20260926-130000.dump"
if POSTGRES_DB=mystic_auth BACKUP_DATABASES=mystic_auth bash "$SCRIPT" "$TEST_DIR" 1 >/dev/null 2>&1; then
  fail "empty newest backup was accepted"
else
  pass "empty newest backup is rejected"
fi

echo "All backup-freshness checks passed."
