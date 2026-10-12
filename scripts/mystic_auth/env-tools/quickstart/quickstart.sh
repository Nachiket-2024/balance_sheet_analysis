#!/usr/bin/env bash
# One command from a fresh clone to a running dev stack with a login you can
# use: runs setup-env if env/mystic_auth/.env.dev doesn't exist yet, brings the
# stack up and waits for it to be healthy, offers to create the system
# superuser, then tails logs like dev-up.sh normally does.
#
# Safe to re-run: setup-env is skipped once env/mystic_auth/.env.dev exists,
# `docker compose up` is idempotent, and system superuser creation is
# opt-in each time.
#
# Usage: ./scripts/mystic_auth/env-tools/quickstart/quickstart.sh   (Git Bash / WSL / Linux / macOS)
# PowerShell: .\scripts\mystic_auth\env-tools\quickstart\quickstart.ps1
# Command Prompt: scripts\mystic_auth\env-tools\quickstart\quickstart.cmd
set -uo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
cd "$REPO_ROOT"

if [ ! -f env/mystic_auth/.env.dev ] || [ ! -f env/app/.env.dev ]; then
  echo "Runtime env files are incomplete: running setup."
  echo
  ./scripts/mystic_auth/env-tools/setup-env/setup-env.sh
  status=$?
  if [ "$status" -ne 0 ]; then
    echo "Environment setup failed; the dev stack was not started." >&2
    exit "$status"
  fi
  echo
fi

echo "Starting the dev stack..."
echo
DEV_UP_TAIL=0 ./scripts/mystic_auth/docker/dev/dev-up.sh
status=$?
if [ "$status" -ne 0 ]; then
  echo
  echo "Stack failed to start. See the error above; nothing further to do here."
  exit "$status"
fi

DC=(docker compose \
  -f docker/mystic_auth/compose/docker-compose.dev.yml \
  -f docker/app/compose/docker-compose.dev.yml \
  --env-file env/mystic_auth/.env.dev \
  --env-file env/app/.env.dev)

env_value() {
  local key="$1"
  local value=""
  local candidate
  for file in env/mystic_auth/.env.dev env/app/.env.dev; do
    [ -f "$file" ] || continue
    candidate="$(awk -F= -v wanted="$key" '$1 == wanted { sub(/^[^=]*=/, ""); value=$0 } END { print value }' "$file")"
    [ -n "$candidate" ] && value="$candidate"
  done
  printf '%s' "$value"
}

FRONTEND_HOST_PORT="$(env_value FRONTEND_HOST_PORT)"
FRONTEND_HOST_PORT="${FRONTEND_HOST_PORT:-5173}"
BACKEND_HOST_PORT="$(env_value BACKEND_HOST_PORT)"
BACKEND_HOST_PORT="${BACKEND_HOST_PORT:-8000}"
BUGSINK_HOST_PORT="$(env_value BUGSINK_HOST_PORT)"
BUGSINK_HOST_PORT="${BUGSINK_HOST_PORT:-8010}"

echo
read -rp "Create the system superuser now? [Y/n] " create_su
create_su="${create_su:-Y}"
if [[ "$create_su" =~ ^[Yy] ]]; then
  "${DC[@]}" exec -it backend python -m mystic_auth.scripts.create_system_user
fi

echo
echo "--- Ready ---"
echo "Frontend:  http://localhost:${FRONTEND_HOST_PORT}"
echo "API docs:  http://localhost:${BACKEND_HOST_PORT}/docs"
echo "Bugsink:   http://localhost:${BUGSINK_HOST_PORT} (error monitoring)"
echo
echo "Still need real values for Google OAuth / SMTP / anything else?"
echo "See docs/mystic_auth/template-usage/overview.md."
echo
echo "Tailing backend + frontend + procrastinate_worker (Ctrl+C stops watching, stack keeps running)."
exec "${DC[@]}" logs -f backend frontend procrastinate_worker
