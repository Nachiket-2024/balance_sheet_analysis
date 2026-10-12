#!/usr/bin/env bash
# Restores an encrypted .dump.enc, a .dump, or legacy .sql backup into the `postgres`
# Docker Compose service. This is destructive because it overwrites rows and
# tables defined by the dump, so it asks for confirmation unless -y/--yes is passed.
# The target database is taken from the dump's filename (<db>-<timestamp>.dump,
# e.g. "bugsink-20260901-020000.dump" restores into "bugsink"), falling back to
# POSTGRES_DB for files that don't follow that naming convention.
#
# Usage: scripts/mystic_auth/db/database-restore/database-restore.sh <backup-file> [compose-file] [-y|--yes]
#   compose-file defaults to docker-compose.dev.yml, and can be given as
#   just a basename (looked up under docker/mystic_auth/compose/) or a full
#   path.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../" && pwd)"
cd "$REPO_ROOT"

BACKUP_FILE=""
COMPOSE_ARG="docker-compose.dev.yml"
ASSUME_YES=false

for arg in "$@"; do
  case "$arg" in
    -y|--yes)
      ASSUME_YES=true
      ;;
    *.yml|*.yaml)
      COMPOSE_ARG="$arg"
      ;;
    *)
      BACKUP_FILE="$arg"
      ;;
  esac
done

if [ -z "$BACKUP_FILE" ]; then
  echo "Usage: scripts/mystic_auth/db/database-restore/database-restore.sh <backup-file> [compose-file] [-y|--yes]" >&2
  exit 1
fi

if [ ! -f "$BACKUP_FILE" ]; then
  echo "Backup file not found: $BACKUP_FILE" >&2
  exit 1
fi

COMPOSE_BASENAME="$(basename "$COMPOSE_ARG")"
case "$COMPOSE_ARG" in
  */*) COMPOSE_FILES=("$COMPOSE_ARG") ;;
  *) COMPOSE_FILES=("docker/mystic_auth/compose/$COMPOSE_BASENAME" "docker/app/compose/$COMPOSE_BASENAME") ;;
esac

# Derived from the filename rather than a fixed list, so a fork's own new
# mode (e.g. docker-compose.staging.yml) resolves to the right env file
# too: "dev" is the one mode with no suffix by convention, every other
# mode's suffix is ".<mode>".
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

DC_ARGS=()
for f in "${COMPOSE_FILES[@]}"; do DC_ARGS+=(-f "$f"); done
for f in "${ENV_FILES[@]}"; do DC_ARGS+=(--env-file "$f"); done

# Derive the target database from the dump's own filename so a
# "bugsink-*.dump" or legacy "bugsink-*.sql" restores into "bugsink" rather than always landing
# in POSTGRES_DB. Falls back to POSTGRES_DB for non-conforming filenames.
BASENAME="$(basename "$BACKUP_FILE")"
if [[ "$BASENAME" =~ ^(.+)-[0-9]{8}-[0-9]{6}\.(dump\.enc|dump|sql)$ ]]; then
  TARGET_DB="${BASH_REMATCH[1]}"
else
  TARGET_DB="$POSTGRES_DB"
fi

if [ "$ASSUME_YES" != true ]; then
  read -r -p "This will overwrite data in database '${TARGET_DB}' with the contents of ${BACKUP_FILE}. Continue? [y/N] " reply
  case "$reply" in
    [yY]|[yY][eE][sS]) ;;
    *) echo "Aborted."; exit 1 ;;
  esac
fi

echo "Restoring '${TARGET_DB}' from ${BACKUP_FILE} via ${COMPOSE_FILES[*]}..."
case "$BACKUP_FILE" in
  *.dump.enc)
    : "${BACKUP_ENCRYPTION_KEY:?BACKUP_ENCRYPTION_KEY must be set to restore encrypted backups}"
    # Verify the detached HMAC tag (see backup-hmac.sh) before decrypting -
    # AES-256-CBC alone has no tamper-evidence of its own. A backup made
    # before this check existed has no .hmac file; warn instead of hard
    # failing so an older legitimate backup can still be restored, but a
    # present-and-wrong tag (actual tampering or corruption) always aborts.
    HMAC_STATUS=0
    "$REPO_ROOT/scripts/mystic_auth/db/backup-verification/backup-hmac.sh" verify "$BACKUP_FILE" "$BACKUP_ENCRYPTION_KEY" || HMAC_STATUS=$?
    if [ "$HMAC_STATUS" -eq 1 ]; then
      echo "FAIL: ${BACKUP_FILE}.hmac does not match this file's contents - it may be corrupted or tampered with. Refusing to restore." >&2
      exit 1
    elif [ "$HMAC_STATUS" -eq 2 ]; then
      echo "WARNING: no ${BACKUP_FILE}.hmac tag found (backup predates tamper-evidence support) - proceeding without integrity verification." >&2
    fi
    openssl enc -d -aes-256-cbc -pbkdf2 -in "$BACKUP_FILE" \
      -pass env:BACKUP_ENCRYPTION_KEY | \
      docker compose "${DC_ARGS[@]}" exec -T postgres \
        pg_restore -U "$POSTGRES_USER" --clean --if-exists --dbname "$TARGET_DB"
    ;;
  *.dump)
    docker compose "${DC_ARGS[@]}" exec -T postgres \
      pg_restore -U "$POSTGRES_USER" --clean --if-exists --dbname "$TARGET_DB" < "$BACKUP_FILE"
    ;;
  *)
    docker compose "${DC_ARGS[@]}" exec -T postgres \
      psql -U "$POSTGRES_USER" "$TARGET_DB" < "$BACKUP_FILE"
    ;;
esac

echo "Restore complete."
