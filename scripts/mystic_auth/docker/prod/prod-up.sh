#!/usr/bin/env bash
# Thin wrapper around `docker compose -f docker/mystic_auth/compose/docker-compose.prod.yml`
# that always passes --env-file env/mystic_auth/.env.prod, so this stack never
# accidentally reads dev's env/mystic_auth/.env.dev (Compose's default env_file for
# interpolation is always a literal ".env" in the working directory unless
# --env-file overrides it).
#
# Forwards all arguments, so this is a drop-in replacement for
# `docker compose -f docker/mystic_auth/compose/docker-compose.prod.yml`, e.g.:
#   scripts/mystic_auth/docker/prod/prod-up.sh up -d --build
#   scripts/mystic_auth/docker/prod/prod-up.sh logs -f frontend
#   scripts/mystic_auth/docker/prod/prod-up.sh exec -it backend python -m mystic_auth.scripts.create_system_user
#
# With no arguments, defaults to `up -d --build`.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
cd "$REPO_ROOT"

if [ "$#" -eq 0 ]; then
  set -- up -d --build
fi

scripts/mystic_auth/env-tools/check-env/check-env.sh \
  env/mystic_auth/.env.prod \
  env/app/.env.prod

exec docker compose \
  -f docker/mystic_auth/compose/docker-compose.prod.yml \
  -f docker/app/compose/docker-compose.prod.yml \
  --env-file env/mystic_auth/.env.prod \
  --env-file env/app/.env.prod \
  "$@"
