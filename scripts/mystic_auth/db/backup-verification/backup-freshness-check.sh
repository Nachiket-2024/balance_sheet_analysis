#!/usr/bin/env bash
# Verify that every required database has a recent, non-empty backup.
#
# This checks backup artifacts rather than the backup container's process
# state. A running service can still be stuck, misconfigured, or unable to
# upload its output. It is intended for an external scheduler or monitoring
# agent and exits non-zero when backup protection cannot be established.
#
# Usage: backup-freshness-check.sh [backup-directory] [max-age-hours]
# Defaults: ./backups, BACKUP_MAX_AGE_HOURS, and twice BACKUP_INTERVAL_HOURS.
# Required databases default to POSTGRES_DB and bugsink.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../" && pwd)"
DEFAULT_BACKUP_DIR="$REPO_ROOT/backups"
BACKUP_DIR="${1:-${BACKUP_DIR:-$DEFAULT_BACKUP_DIR}}"

if [ -n "${2:-}" ]; then
  MAX_AGE_HOURS="$2"
elif [ -n "${BACKUP_MAX_AGE_HOURS:-}" ]; then
  MAX_AGE_HOURS="$BACKUP_MAX_AGE_HOURS"
else
  BACKUP_INTERVAL_HOURS="${BACKUP_INTERVAL_HOURS:-12}"
  MAX_AGE_HOURS="$((BACKUP_INTERVAL_HOURS * 2))"
fi

if ! [[ "$MAX_AGE_HOURS" =~ ^[1-9][0-9]*$ ]]; then
  echo "FAIL: max backup age must be a positive whole number of hours: '$MAX_AGE_HOURS'" >&2
  exit 2
fi

if [ ! -d "$BACKUP_DIR" ]; then
  echo "FAIL: backup directory does not exist: $BACKUP_DIR" >&2
  exit 1
fi

POSTGRES_DB="${POSTGRES_DB:-mystic_auth}"
BACKUP_DATABASES="${BACKUP_DATABASES:-$POSTGRES_DB bugsink}"
NOW="$(date +%s)"
MAX_AGE_SECONDS=$((MAX_AGE_HOURS * 3600))
MAX_FUTURE_SECONDS="${BACKUP_MAX_FUTURE_SECONDS:-300}"

if ! [[ "$MAX_FUTURE_SECONDS" =~ ^[0-9]+$ ]]; then
  echo "FAIL: BACKUP_MAX_FUTURE_SECONDS must be a non-negative whole number" >&2
  exit 2
fi

find_latest_backup() {
  local database="$1"
  find "$BACKUP_DIR" -maxdepth 1 -type f \
    \( -name "${database}-*.dump.enc" -o -name "${database}-*.dump" -o -name "${database}-*.sql" \) \
    -printf '%T@ %p\n' | sort -nr | head -n1 | cut -d' ' -f2-
}

FAILURES=0
for database in $BACKUP_DATABASES; do
  if ! [[ "$database" =~ ^[A-Za-z0-9_.-]+$ ]]; then
    echo "FAIL: invalid database name in BACKUP_DATABASES: '$database'" >&2
    FAILURES=$((FAILURES + 1))
    continue
  fi

  backup_file="$(find_latest_backup "$database")"
  if [ -z "$backup_file" ]; then
    echo "FAIL: no backup found for database '$database' in $BACKUP_DIR" >&2
    FAILURES=$((FAILURES + 1))
    continue
  fi

  file_mtime="$(stat -c '%Y' -- "$backup_file")"
  age_seconds=$((NOW - file_mtime))
  if [ "$age_seconds" -lt "$((0 - MAX_FUTURE_SECONDS))" ]; then
    echo "FAIL: backup for '$database' is too far in the future: $backup_file" >&2
    FAILURES=$((FAILURES + 1))
    continue
  fi
  if [ "$age_seconds" -gt "$MAX_AGE_SECONDS" ]; then
    echo "FAIL: newest backup for '$database' is ${age_seconds}s old (limit ${MAX_AGE_SECONDS}s): $backup_file" >&2
    FAILURES=$((FAILURES + 1))
    continue
  fi
  if [ ! -s "$backup_file" ]; then
    echo "FAIL: newest backup for '$database' is empty: $backup_file" >&2
    FAILURES=$((FAILURES + 1))
    continue
  fi

  echo "OK: '$database' has a non-empty backup from $(date -d "@$file_mtime" '+%Y-%m-%d %H:%M:%S %Z') ($backup_file)"
done

if [ "$FAILURES" -ne 0 ]; then
  echo "FAIL: backup freshness check found $FAILURES problem(s)." >&2
  exit 1
fi

echo "OK: all required database backups are fresh (max age ${MAX_AGE_HOURS}h)."
