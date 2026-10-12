#!/usr/bin/env bash
# Starts only the Docker data services, derives host-reachable connection URLs
# from their configured published ports, runs migrations, and starts Uvicorn
# from the host for debugger-friendly backend development.
#
# Usage: scripts/mystic_auth/docker/dev/backend-host-run.sh [uvicorn args...]
set -euo pipefail

REPO_ROOT="${BACKEND_HOST_RUN_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)}"
cd "$REPO_ROOT"

DC=(docker compose \
  -f docker/mystic_auth/compose/docker-compose.dev.yml \
  -f docker/app/compose/docker-compose.dev.yml \
  --env-file env/mystic_auth/.env.dev \
  --env-file env/app/.env.dev)

read_env_value() {
    local key="$1"
    local file value line
    value=""
    for file in env/mystic_auth/.env.dev env/app/.env.dev; do
        [ -f "$file" ] || continue
        while IFS= read -r line; do
            case "$line" in
                "$key="*) value="${line#*=}" ;;
            esac
        done < "$file"
    done
    printf '%s' "$value"
}

rewrite_host_url() {
    local url="$1"
    local postgres_port="$2"
    local valkey_port="$3"
    url="$(printf '%s' "$url" | sed -E "s#@postgres:[0-9]+#@localhost:${postgres_port}#; s#//postgres:[0-9]+/#//localhost:${postgres_port}/#; s#@valkey:[0-9]+#@localhost:${valkey_port}#; s#//valkey:[0-9]+/#//localhost:${valkey_port}/#")"
    printf '%s' "$url"
}

POSTGRES_HOST_PORT="$(read_env_value POSTGRES_HOST_PORT)"
VALKEY_HOST_PORT="$(read_env_value VALKEY_HOST_PORT)"
POSTGRES_HOST_PORT="${POSTGRES_HOST_PORT:-5433}"
VALKEY_HOST_PORT="${VALKEY_HOST_PORT:-6380}"

"${DC[@]}" up -d --wait postgres valkey

export DATABASE_URL
DATABASE_URL="$(rewrite_host_url "$(read_env_value DATABASE_URL)" "$POSTGRES_HOST_PORT" "$VALKEY_HOST_PORT")"
export APP_DATABASE_URL
APP_DATABASE_URL="$(rewrite_host_url "$(read_env_value APP_DATABASE_URL)" "$POSTGRES_HOST_PORT" "$VALKEY_HOST_PORT")"
export VALKEY_URL
VALKEY_URL="$(rewrite_host_url "$(read_env_value VALKEY_URL)" "$POSTGRES_HOST_PORT" "$VALKEY_HOST_PORT")"

export ALEMBIC_CONFIG="$REPO_ROOT/backend/alembic.ini"
export PYTHONPATH="$REPO_ROOT/backend${PYTHONPATH:+:$PYTHONPATH}"

(cd backend && alembic upgrade head)
exec uvicorn app.main:app --reload "$@"
