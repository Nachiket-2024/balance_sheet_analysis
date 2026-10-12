#!/usr/bin/env bash
# Dumps the `postgres` Compose service's app database and its bugsink
# database (error monitoring, see docker/mystic_auth/postgres-init/init-bugsink-db.sh)
# to timestamped encrypted .dump.enc files under backups/. Reads POSTGRES_USER/POSTGRES_DB
# from the env file matching the given compose file.
#
# Usage: scripts/mystic_auth/db/database-backup/database-backup.sh [compose-file]
#   compose-file defaults to docker-compose.dev.yml, and can be given as
#   just a basename (looked up under docker/mystic_auth/compose/) or a full
#   path.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../" && pwd)"
cd "$REPO_ROOT"

COMPOSE_ARG="${1:-docker-compose.dev.yml}"
COMPOSE_BASENAME="$(basename "$COMPOSE_ARG")"
case "$COMPOSE_ARG" in
  */*) COMPOSE_FILES=("$COMPOSE_ARG") ;;
  *) COMPOSE_FILES=("docker/mystic_auth/compose/$COMPOSE_BASENAME" "docker/app/compose/$COMPOSE_BASENAME") ;;
esac

# Derived from the filename rather than a fixed list, so a fork's own new
# mode (e.g. docker-compose.staging.yml) resolves to the right env file
# too: every mode has an explicit suffix (`.dev`, `.prod`, `.local-prod-*`).
MODE="${COMPOSE_BASENAME#docker-compose.}"
MODE="${MODE%.yml}"
if [ "$MODE" = "dev" ]; then
  ENV_SUFFIX=".dev"
else
  ENV_SUFFIX=".${MODE}"
fi
ENV_FILE="env/mystic_auth/.env${ENV_SUFFIX}"
APP_ENV_FILE="env/app/.env${ENV_SUFFIX}"
ENV_FILES=("$ENV_FILE" "$APP_ENV_FILE")

# Pull just these two vars by name rather than sourcing the whole file:
# some values (e.g. GMAIL_APP_PASSWORD) have unquoted spaces that break
# `source` but are fine for python-dotenv/pydantic. Checked in app/ then
# mystic_auth/ so a fork's override wins.
if [ -z "${POSTGRES_USER:-}" ]; then
  POSTGRES_USER="$(grep -hm1 '^POSTGRES_USER=' "$APP_ENV_FILE" "$ENV_FILE" 2>/dev/null | head -n1 | cut -d= -f2-)"
fi
if [ -z "${POSTGRES_DB:-}" ]; then
  POSTGRES_DB="$(grep -hm1 '^POSTGRES_DB=' "$APP_ENV_FILE" "$ENV_FILE" 2>/dev/null | head -n1 | cut -d= -f2-)"
fi
if [ -z "${BACKUP_ENCRYPTION_KEY:-}" ]; then
  BACKUP_ENCRYPTION_KEY="$(grep -hm1 '^BACKUP_ENCRYPTION_KEY=' "$APP_ENV_FILE" "$ENV_FILE" 2>/dev/null | head -n1 | cut -d= -f2-)"
  export BACKUP_ENCRYPTION_KEY
fi

: "${POSTGRES_USER:?POSTGRES_USER must be set (check $ENV_FILE)}"
: "${POSTGRES_DB:?POSTGRES_DB must be set (check $ENV_FILE)}"
: "${BACKUP_ENCRYPTION_KEY:?BACKUP_ENCRYPTION_KEY must be set for encrypted backups}"

DC_ARGS=()
for f in "${COMPOSE_FILES[@]}"; do DC_ARGS+=(-f "$f"); done
for f in "${ENV_FILES[@]}"; do DC_ARGS+=(--env-file "$f"); done

BACKUP_DIR="${BACKUP_DIR:-$REPO_ROOT/backups}"
mkdir -p "$BACKUP_DIR"
if [ ! -w "$BACKUP_DIR" ]; then
  echo "Backup directory is not writable by $(id -un): $BACKUP_DIR" >&2
  echo "Use BACKUP_DIR=/path/to/writable/dir or fix the bind-mount ownership before retrying." >&2
  exit 1
fi

alert_backup_failure() {
  "$REPO_ROOT/scripts/mystic_auth/db/database-backup/database-backup-failure-alert.sh" "$1" || true
}

TIMESTAMP="$(date +%Y%m%d-%H%M%S)"

for DB in "$POSTGRES_DB" bugsink; do
  BACKUP_FILE="$BACKUP_DIR/${DB}-${TIMESTAMP}.dump.enc"
  TEMP_BACKUP_FILE="${BACKUP_FILE}.tmp.$$"
  echo "Backing up database '${DB}' via ${COMPOSE_FILES[*]}..."
  # No --file=-: on this image's pg_dump build, "-" as a literal filename
  # argument produces a 0-byte file instead of writing to stdout (a real
  # bug caught building the restore-drill test, see
  # scripts/mystic_auth/db/database-restore/database-restore-drill.sh). Omitting --file entirely
  # defaults to stdout, which this redirect already captures, and works
  # portably regardless of that behavior.
  if ! docker compose "${DC_ARGS[@]}" exec -T postgres \
    pg_dump -U "$POSTGRES_USER" --format=custom "$DB" | \
    openssl enc -aes-256-cbc -pbkdf2 -salt -out "$TEMP_BACKUP_FILE" \
      -pass env:BACKUP_ENCRYPTION_KEY; then
    rm -f -- "$TEMP_BACKUP_FILE"
    alert_backup_failure "pg_dump failed for $DB"
    exit 1
  fi
  if ! docker compose "${DC_ARGS[@]}" exec -T postgres \
    pg_restore --list >/dev/null < <(openssl enc -d -aes-256-cbc -pbkdf2 -in "$TEMP_BACKUP_FILE" \
      -pass env:BACKUP_ENCRYPTION_KEY); then
    rm -f -- "$TEMP_BACKUP_FILE"
    alert_backup_failure "pg_restore --list failed for $BACKUP_FILE"
    exit 1
  fi
  # AES-256-CBC has no authenticated-encryption mode of its own (openssl
  # enc's AEAD ciphers aren't supported by the enc subcommand at all - see
  # backup-hmac.sh's own comment). This detached HMAC-SHA256 tag is the
  # tamper-evidence CBC alone doesn't provide; database-restore.sh verifies it
  # before decrypting a real restore.
  if ! "$REPO_ROOT/scripts/mystic_auth/db/backup-verification/backup-hmac.sh" tag "$TEMP_BACKUP_FILE" "$BACKUP_ENCRYPTION_KEY"; then
    rm -f -- "$TEMP_BACKUP_FILE"
    alert_backup_failure "HMAC tagging failed for $BACKUP_FILE"
    exit 1
  fi
  mv -f -- "$TEMP_BACKUP_FILE" "$BACKUP_FILE"
  mv -f -- "$TEMP_BACKUP_FILE.hmac" "$BACKUP_FILE.hmac"
  echo "Backup written to $BACKUP_FILE ($(du -h "$BACKUP_FILE" | cut -f1))"

  # Same optional off-host upload hook as the db_backup Compose service
  # (docker-compose.prod.yml and the local-prod-* variants), so a manual
  # backup ships off-host the same way a scheduled one does. Uploads the
  # .hmac tag alongside the ciphertext - see backup-upload.sh.
  if [ -n "${BACKUP_UPLOAD_COMMAND:-}" ]; then
    echo "Running BACKUP_UPLOAD_COMMAND for encrypted $BACKUP_FILE..."
    if ! "$REPO_ROOT/scripts/mystic_auth/db/backup-upload/backup-upload.sh" "$BACKUP_FILE"; then
      alert_backup_failure "off-host upload failed for $BACKUP_FILE"
      exit 1
    fi
  fi
done
