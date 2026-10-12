#!/usr/bin/env bash
# Thin wrapper around `docker compose -f
# docker/mystic_auth/compose/docker-compose.local-prod-tailscale.yml` that always passes
# --env-file env/mystic_auth/.env.local-prod-tailscale, so this stack never accidentally
# reads dev's env/mystic_auth/.env.dev.
#
# Forwards all arguments, e.g.:
#   scripts/mystic_auth/docker/local-prod-tailscale/local-prod-tailscale-up.sh up -d --build
#   scripts/mystic_auth/docker/local-prod-tailscale/local-prod-tailscale-up.sh logs -f frontend
#
# See local-prod-cloudflare-up.sh / local-prod-ngrok-up.sh for the other two
# local-prod tunnel variants. With no arguments, defaults to `up -d --build`.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
cd "$REPO_ROOT"

if [ "$#" -eq 0 ]; then
  set -- up -d --build
fi

scripts/mystic_auth/env-tools/check-env/check-env.sh \
  env/mystic_auth/.env.local-prod-tailscale \
  env/app/.env.local-prod-tailscale

exec docker compose \
  -f docker/mystic_auth/compose/docker-compose.local-prod-tailscale.yml \
  -f docker/app/compose/docker-compose.local-prod-tailscale.yml \
  --env-file env/mystic_auth/.env.local-prod-tailscale \
  --env-file env/app/.env.local-prod-tailscale \
  "$@"
