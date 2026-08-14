#!/usr/bin/env bash
# Non-interactively bootstraps the system superuser against the prod stack
# (docker-compose.prod.yml). Fill in local-scripts/prod/system-user.env
# first, with a real production email/password, not the dev placeholder.
# Assumes a fresh account (no existing user with that email) : this pipes a
# fixed 3-line stdin (email, name, password) matching create_system_user.py's
# "brand new account" prompt sequence. If the account already exists, run
# `docker compose -f docker-compose.prod.yml exec backend python -m mystic_auth.scripts.create_system_user`
# by hand instead, since that branch asks different questions.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR/../.."

source "$SCRIPT_DIR/system-user.env"

printf '%s\n%s\n%s\n' "$SYSTEM_USER_EMAIL" "$SYSTEM_USER_NAME" "$SYSTEM_USER_PASSWORD" \
  | docker compose -f docker-compose.prod.yml exec -T backend python -m mystic_auth.scripts.create_system_user
