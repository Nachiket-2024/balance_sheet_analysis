#!/usr/bin/env bash
# Exercise the real encrypted manual-backup path against the CI database.
# This deliberately uses a temporary host directory so the test never depends
# on bind-mount ownership or writes into the repository's backup archive.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
cd "$REPO_ROOT"

BACKUP_DIR_TEST="$(mktemp -d)"
trap 'rm -rf -- "$BACKUP_DIR_TEST"' EXIT
COMPOSE_FILE="${BACKUP_TEST_COMPOSE_FILE:-docker-compose.dev.yml}"

# Keep the regression test aligned with database-backup.sh: downstream apps
# may deliberately use a different application database name (for example,
# `example_app_db`). The backup script already reads POSTGRES_DB from the mode's
# env files, so the test must inspect the same value instead of assuming the
# MysticAuth template default.
COMPOSE_BASENAME="$(basename "$COMPOSE_FILE")"
MODE="${COMPOSE_BASENAME#docker-compose.}"
MODE="${MODE%.yml}"
if [ "$MODE" = "dev" ]; then
  ENV_SUFFIX=".dev"
else
  ENV_SUFFIX=".${MODE}"
fi
ENV_FILE="env/mystic_auth/.env${ENV_SUFFIX}"
APP_ENV_FILE="env/app/.env${ENV_SUFFIX}"
POSTGRES_DB="${POSTGRES_DB:-$(grep -hm1 '^POSTGRES_DB=' "$APP_ENV_FILE" "$ENV_FILE" 2>/dev/null | head -n1 | cut -d= -f2-)}"
: "${POSTGRES_DB:?POSTGRES_DB must be set (check $ENV_FILE)}"

echo "=== create and structurally verify encrypted backups ==="
# The disposable check must also work against an older local .env.dev that
# predates encrypted backups. Never write this generated key back to env files.
# Captured in this shell (not just passed as a one-off prefix to database-backup.sh)
# so the HMAC verification below can reuse the same key.
BACKUP_ENCRYPTION_KEY="${BACKUP_ENCRYPTION_KEY:-$(openssl rand -hex 32)}"
export BACKUP_ENCRYPTION_KEY
BACKUP_DIR="$BACKUP_DIR_TEST" BACKUP_UPLOAD_COMMAND= \
  bash scripts/mystic_auth/db/database-backup/database-backup.sh "$COMPOSE_FILE"

for database in "$POSTGRES_DB" bugsink; do
  files=("$BACKUP_DIR_TEST/$database-"*.dump.enc)
  if [ "${#files[@]}" -ne 1 ] || [ ! -s "${files[0]}" ]; then
    echo "FAIL: expected one non-empty encrypted backup for '$database'" >&2
    exit 1
  fi
  if grep -a -q 'PGDMP' "${files[0]}"; then
    echo "FAIL: '$database' backup appears to contain plaintext custom-format data" >&2
    exit 1
  fi
  if [ ! -s "${files[0]}.hmac" ]; then
    echo "FAIL: expected a non-empty '${files[0]}.hmac' tamper-evidence tag alongside '$database' backup" >&2
    exit 1
  fi
  if ! bash scripts/mystic_auth/db/backup-verification/backup-hmac.sh verify "${files[0]}" "$BACKUP_ENCRYPTION_KEY"; then
    echo "FAIL: HMAC tag for '$database' backup does not verify against its own ciphertext" >&2
    exit 1
  fi
done
echo "OK: both databases produced non-empty encrypted dumps with a verifying HMAC tag"

echo "=== verify freshness monitoring against the generated artifacts ==="
BACKUP_DATABASES="$POSTGRES_DB bugsink" \
  bash scripts/mystic_auth/db/backup-verification/backup-freshness-check.sh "$BACKUP_DIR_TEST" 1

echo "All encrypted backup round-trip checks passed."
