#!/usr/bin/env bash
# Proves a backup is actually restorable, not just present: dumps the
# running app database, restores that dump into a disposable scratch
# database on the same Postgres server (never overwriting the real one),
# runs a smoke query against it plus a full per-table row-count parity
# check, then drops the scratch database. Exits non-zero on any failure, so
# a broken backup or restore path fails loudly instead of only being
# discovered during a real incident.
#
# database-backup.sh already verifies a dump's *structure* with `pg_restore
# --list`; this goes one step further and proves the dump's *contents* come
# back as a real, queryable database.
#
# Usage: scripts/mystic_auth/db/database-restore/database-restore-drill.sh [compose-file]
#   compose-file defaults to docker-compose.dev.yml, and can be given as
#   just a basename (looked up under docker/mystic_auth/compose/) or a full
#   path. Needs a running `postgres` service on that compose file.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../" && pwd)"
cd "$REPO_ROOT"

COMPOSE_ARG="${1:-docker-compose.dev.yml}"
COMPOSE_BASENAME="$(basename "$COMPOSE_ARG")"
case "$COMPOSE_ARG" in
  */*) COMPOSE_FILES=("$COMPOSE_ARG") ;;
  *) COMPOSE_FILES=("docker/mystic_auth/compose/$COMPOSE_BASENAME" "docker/app/compose/$COMPOSE_BASENAME") ;;
esac

# Same env-file resolution as database-backup.sh/database-restore.sh - see their own
# comments for why this is done by name, not `source`.
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

# Fixed name, not timestamped: a drill run cleans up after itself
# (including on failure, via the trap below), so there's never a reason for
# more than one to exist at a time, and a fixed name makes a leftover from
# a killed run obvious and easy to drop by hand.
SCRATCH_DB="${POSTGRES_DB}_restore_drill"
DRILL_DUMP="$(mktemp --suffix=.dump.enc)"
: "${BACKUP_ENCRYPTION_KEY:?BACKUP_ENCRYPTION_KEY must be set for encrypted restore drills}"

cleanup() {
  rm -f "$DRILL_DUMP"
  docker compose "${DC_ARGS[@]}" exec -T postgres \
    psql -U "$POSTGRES_USER" -d postgres -c "DROP DATABASE IF EXISTS ${SCRATCH_DB};" >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "1/5  Dumping '${POSTGRES_DB}'..."
# No --file=-: see database-backup.sh's own comment on this same line - it
# produces a 0-byte dump on this image's pg_dump build instead of writing
# to stdout. Omitting --file defaults to stdout, which this redirect
# captures.
docker compose "${DC_ARGS[@]}" exec -T postgres \
  pg_dump -U "$POSTGRES_USER" --format=custom "$POSTGRES_DB" | \
  openssl enc -aes-256-cbc -pbkdf2 -salt -out "$DRILL_DUMP" \
    -pass env:BACKUP_ENCRYPTION_KEY

echo "2/5  Creating scratch database '${SCRATCH_DB}'..."
docker compose "${DC_ARGS[@]}" exec -T postgres \
  psql -U "$POSTGRES_USER" -d postgres -c "DROP DATABASE IF EXISTS ${SCRATCH_DB};" >/dev/null
docker compose "${DC_ARGS[@]}" exec -T postgres \
  psql -U "$POSTGRES_USER" -d postgres -c "CREATE DATABASE ${SCRATCH_DB};" >/dev/null

echo "3/5  Restoring the dump into '${SCRATCH_DB}'..."
docker compose "${DC_ARGS[@]}" exec -T postgres \
  pg_restore -U "$POSTGRES_USER" --dbname "$SCRATCH_DB" < <(openssl enc -d \
    -aes-256-cbc -pbkdf2 -in "$DRILL_DUMP" -pass env:BACKUP_ENCRYPTION_KEY)

echo "4/5  Smoke-checking the restored database..."
# alembic_version existing and non-empty proves the schema, not just raw
# bytes, came back: a dump that restored an empty/corrupt database would
# fail this even if pg_restore itself printed no error.
ALEMBIC_ROWS="$(docker compose "${DC_ARGS[@]}" exec -T postgres \
  psql -U "$POSTGRES_USER" -d "$SCRATCH_DB" -tAc "SELECT count(*) FROM alembic_version;")"
if [ "$(echo "$ALEMBIC_ROWS" | tr -d '[:space:]')" -lt 1 ]; then
  echo "FAIL: alembic_version has no rows in the restored database - schema did not come back intact." >&2
  exit 1
fi

USERS_TABLE_EXISTS="$(docker compose "${DC_ARGS[@]}" exec -T postgres \
  psql -U "$POSTGRES_USER" -d "$SCRATCH_DB" -tAc "SELECT to_regclass('public.users') IS NOT NULL;")"
if [ "$(echo "$USERS_TABLE_EXISTS" | tr -d '[:space:]')" != "t" ]; then
  echo "FAIL: users table missing in the restored database." >&2
  exit 1
fi

echo "5/5  Comparing per-table row counts against the source database..."
# Schema-only checks (alembic_version, users existing) can pass on a
# silent partial restore - e.g. pg_restore skipping a table after a
# mid-stream error but still exiting 0 for the rest. Counting every public
# table in both databases and diffing them catches that class of bug that
# the two checks above would miss.
TABLES="$(docker compose "${DC_ARGS[@]}" exec -T postgres \
  psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc \
  "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename;" | tr -d '\r')"

MISMATCH=0
while IFS= read -r TABLE; do
  [ -z "$TABLE" ] && continue
  SOURCE_COUNT="$(docker compose "${DC_ARGS[@]}" exec -T postgres \
    psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc "SELECT count(*) FROM \"${TABLE}\";" | tr -d '[:space:]')"
  RESTORED_COUNT="$(docker compose "${DC_ARGS[@]}" exec -T postgres \
    psql -U "$POSTGRES_USER" -d "$SCRATCH_DB" -tAc "SELECT count(*) FROM \"${TABLE}\";" | tr -d '[:space:]')"
  if [ "$SOURCE_COUNT" != "$RESTORED_COUNT" ]; then
    echo "FAIL: table '${TABLE}' has ${SOURCE_COUNT} rows in '${POSTGRES_DB}' but ${RESTORED_COUNT} in the restored database." >&2
    MISMATCH=1
  fi
done <<< "$TABLES"

if [ "$MISMATCH" -ne 0 ]; then
  echo "FAIL: restored database has row-count mismatches against the source - see above." >&2
  exit 1
fi

echo "OK: dump of '${POSTGRES_DB}' restores cleanly with its schema and full row-count parity intact."
