#!/usr/bin/env sh
# Report a backup failure through the same Sentry protocol used by the
# backend. Bugsink accepts this endpoint, so the backup service does not need
# to depend on Python or invent a second alerting integration.
set -u

MESSAGE="${1:-database backup failed}"
DSN="${BACKUP_SENTRY_DSN:-${SENTRY_DSN:-}}"

[ -n "$DSN" ] || exit 0
case "$DSN" in
  http://*|https://*) ;;
  *) exit 0 ;;
esac

DSN_REST="${DSN#*://}"
KEY="${DSN_REST%%@*}"
TARGET="${DSN_REST#*@}"
HOST="${TARGET%/*}"
PROJECT_ID="${TARGET##*/}"
BASE_URL="${DSN%%://*}://${HOST}"

# This is deliberately best-effort. The original backup error must remain the
# process exit status even when Bugsink is unavailable at the same time.
curl --fail --silent --show-error --max-time 10 \
  -X POST "${BASE_URL}/api/${PROJECT_ID}/store/" \
  -H "X-Sentry-Auth: Sentry sentry_version=7, sentry_key=${KEY}, sentry_client=mystic-auth-backup/1" \
  -H 'Content-Type: application/json' \
  --data "{\"message\":\"${MESSAGE}\",\"level\":\"error\",\"logger\":\"mystic_auth.backup\",\"tags\":{\"component\":\"db_backup\"}}" \
  >/dev/null 2>&1 || true
