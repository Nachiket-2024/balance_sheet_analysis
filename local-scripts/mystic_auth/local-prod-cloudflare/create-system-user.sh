#!/usr/bin/env bash
# Non-interactively bootstraps the system superuser against the local-prod
# cloudflare stack. Fill in local-scripts/mystic_auth/local-prod-cloudflare/system-user.env first.
# Assumes a fresh account: pipes a fixed 3-line stdin (email, name, password)
# matching create_system_user.py's "brand new account" prompt. If the account
# already exists, run this by hand instead (it asks different questions):
# `docker compose -f docker/mystic_auth/compose/docker-compose.local-prod-cloudflare.yml -f docker/app/compose/docker-compose.local-prod-cloudflare.yml --env-file env/mystic_auth/.env.local-prod-cloudflare --env-file env/app/.env.local-prod-cloudflare exec backend python -m mystic_auth.scripts.create_system_user`
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR/../../.."

read_env_value() {
  local key="$1" file="$2"
  grep -m1 "^${key}=" "$file" | cut -d= -f2-
}

ENV_FILE="$SCRIPT_DIR/system-user.env"
[ -f "$ENV_FILE" ] || { echo "Missing $ENV_FILE. Copy system-user.env.example first." >&2; exit 1; }

SYSTEM_USER_EMAIL="$(read_env_value SYSTEM_USER_EMAIL "$ENV_FILE")"
SYSTEM_USER_NAME="$(read_env_value SYSTEM_USER_NAME "$ENV_FILE")"
SYSTEM_USER_PASSWORD="$(read_env_value SYSTEM_USER_PASSWORD "$ENV_FILE")"

: "${SYSTEM_USER_EMAIL:?SYSTEM_USER_EMAIL must be set in $ENV_FILE}"
: "${SYSTEM_USER_NAME:?SYSTEM_USER_NAME must be set in $ENV_FILE}"
: "${SYSTEM_USER_PASSWORD:?SYSTEM_USER_PASSWORD must be set in $ENV_FILE}"

printf '%s\n%s\n%s\n' "$SYSTEM_USER_EMAIL" "$SYSTEM_USER_NAME" "$SYSTEM_USER_PASSWORD" \
  | docker compose -f docker/mystic_auth/compose/docker-compose.local-prod-cloudflare.yml -f docker/app/compose/docker-compose.local-prod-cloudflare.yml --env-file env/mystic_auth/.env.local-prod-cloudflare --env-file env/app/.env.local-prod-cloudflare exec -T backend python -m mystic_auth.scripts.create_system_user
