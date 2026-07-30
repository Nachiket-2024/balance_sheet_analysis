#!/usr/bin/env bash
# Restores a .sql dump (produced by scripts/db_backup.sh) into the `postgres`
# Docker Compose service. Destructive — overwrites existing rows/tables that
# the dump also defines — so it asks for confirmation unless -y/--yes is passed.
#
# Usage: scripts/db_restore.sh <backup-file> [compose-file] [-y|--yes]
#   compose-file defaults to docker-compose.yml.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

BACKUP_FILE=""
COMPOSE_FILE="docker-compose.yml"
ASSUME_YES=false

for arg in "$@"; do
  case "$arg" in
    -y|--yes)
      ASSUME_YES=true
      ;;
    *.yml|*.yaml)
      COMPOSE_FILE="$arg"
      ;;
    *)
      BACKUP_FILE="$arg"
      ;;
  esac
done

if [ -z "$BACKUP_FILE" ]; then
  echo "Usage: scripts/db_restore.sh <backup-file> [compose-file] [-y|--yes]" >&2
  exit 1
fi

if [ ! -f "$BACKUP_FILE" ]; then
  echo "Backup file not found: $BACKUP_FILE" >&2
  exit 1
fi

# Only pull the two vars we need, by name, rather than sourcing the whole
# .env file — some values (e.g. GMAIL_APP_PASSWORD) contain unquoted spaces
# that are valid to python-dotenv/pydantic but break a shell `source`.
if [ -z "${POSTGRES_USER:-}" ] && [ -f .env ]; then
  POSTGRES_USER="$(grep -m1 '^POSTGRES_USER=' .env | cut -d= -f2-)"
fi
if [ -z "${POSTGRES_DB:-}" ] && [ -f .env ]; then
  POSTGRES_DB="$(grep -m1 '^POSTGRES_DB=' .env | cut -d= -f2-)"
fi

: "${POSTGRES_USER:?POSTGRES_USER must be set (check .env)}"
: "${POSTGRES_DB:?POSTGRES_DB must be set (check .env)}"

if [ "$ASSUME_YES" != true ]; then
  read -r -p "This will overwrite data in database '${POSTGRES_DB}' with the contents of ${BACKUP_FILE}. Continue? [y/N] " reply
  case "$reply" in
    [yY]|[yY][eE][sS]) ;;
    *) echo "Aborted."; exit 1 ;;
  esac
fi

echo "Restoring '${POSTGRES_DB}' from ${BACKUP_FILE} via ${COMPOSE_FILE}..."
docker compose -f "$COMPOSE_FILE" exec -T postgres \
  psql -U "$POSTGRES_USER" "$POSTGRES_DB" < "$BACKUP_FILE"

echo "Restore complete."
