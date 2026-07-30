#!/usr/bin/env bash
# Dumps the Postgres database running in the `postgres` Docker Compose
# service to a timestamped .sql file under backups/. Environment-driven
# (reads POSTGRES_USER/POSTGRES_DB from .env) — no cloud/provider assumptions.
#
# Usage: scripts/db_backup.sh [compose-file]
#   compose-file defaults to docker-compose.yml; pass docker-compose.prod.yml
#   to back up a production stack instead.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

COMPOSE_FILE="${1:-docker-compose.yml}"

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

BACKUP_DIR="$REPO_ROOT/backups"
mkdir -p "$BACKUP_DIR"

TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP_FILE="$BACKUP_DIR/${POSTGRES_DB}-${TIMESTAMP}.sql"

echo "Backing up database '${POSTGRES_DB}' via ${COMPOSE_FILE}..."
docker compose -f "$COMPOSE_FILE" exec -T postgres \
  pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" > "$BACKUP_FILE"

echo "Backup written to $BACKUP_FILE ($(du -h "$BACKUP_FILE" | cut -f1))"
