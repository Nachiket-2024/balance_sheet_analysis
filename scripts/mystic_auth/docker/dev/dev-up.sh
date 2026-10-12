#!/usr/bin/env bash
# Starts the full stack, waits for long-running services, and prints a status
# table before tailing focused logs (backend, frontend, procrastinate_worker
# only, skipping DB/Valkey/Bugsink health-check noise).
# Polls services directly instead of `docker compose up --wait`, since
# alembic/bugsink-seed are one-shot containers meant to exit after startup.
#
# Recommended day-to-day command, see README.md. Use plain `docker compose
# up` when you want every service's full logs in one stream.
#
# Usage: ./scripts/mystic_auth/docker/dev/dev-up.sh   (Git Bash or WSL on Windows)
# PowerShell: .\scripts\mystic_auth\docker\dev\dev-up.ps1
# Command Prompt: scripts\mystic_auth\docker\dev\dev-up.cmd
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
cd "$REPO_ROOT"

# Compose files/env files live under docker/ and env/, so every invocation
# below needs the flags explicitly (Compose's bare-invocation defaults only
# look in the current directory). Two -f/--env-file pairs: mystic_auth (the
# template) plus app (yours, ships empty).
DC=(docker compose \
  -f docker/mystic_auth/compose/docker-compose.dev.yml \
  -f docker/app/compose/docker-compose.dev.yml \
  --env-file env/mystic_auth/.env.dev \
  --env-file env/app/.env.dev)

# frontend has no healthcheck in docker-compose.dev.yml, so "Up" is as
# ready as it gets. Every other long-running service does have one.
LONG_RUNNING_SERVICES=(postgres valkey bugsink backend procrastinate_worker frontend)

# GeoIP is opt-in. When the dev env requests it, include the Compose profile
# automatically so the updater provisions the shared database before login
# tests; a configured path without the profile would leave readiness unhealthy.
if awk -F= '$1 == "GEOIP_DB_PATH" && $2 != "" { found=1 } END { exit !found }' env/mystic_auth/.env.dev; then
  if ! awk -F= '
    $1 == "GEOIPUPDATE_ACCOUNT_ID" && $2 != "" { account=1 }
    $1 == "GEOIPUPDATE_LICENSE_KEY" && $2 != "" { license=1 }
    END { exit !(account && license) }
  ' env/mystic_auth/.env.dev; then
    echo "ERROR: GEOIP_DB_PATH is set in env/mystic_auth/.env.dev, but GEOIPUPDATE_ACCOUNT_ID and GEOIPUPDATE_LICENSE_KEY are both required for the GeoIP updater." >&2
    echo "Set both MaxMind credentials or clear GEOIP_DB_PATH before running dev-up.sh." >&2
    exit 1
  fi
  DC+=(--profile geoip)
  LONG_RUNNING_SERVICES+=(geoipupdate)
fi
TIMEOUT_SECONDS=180
POLL_INTERVAL=2
TAIL_SINCE="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

is_ready() {
    local status
    status="$("${DC[@]}" ps --format '{{.Status}}' "$1" 2>/dev/null)"
    case "$status" in
        *"(healthy)"*) return 0 ;;
        "Up "*) [ "$1" = "frontend" ] && return 0 || return 1 ;;
        *) return 1 ;;
    esac
}

is_failed() {
    local status
    status="$("${DC[@]}" ps --format '{{.Status}}' "$1" 2>/dev/null)"
    case "$status" in
        *"Exited"*|*"Restarting"*|"") return 0 ;;
        *) return 1 ;;
    esac
}

# --quiet-pull suppresses Compose's repainting pull-progress table. Real pull
# errors still surface through this command's exit code.
"${DC[@]}" up -d --quiet-pull

# Restart these services so the final tail always includes fresh startup
# banners, even when Compose reused already-running containers.
"${DC[@]}" restart backend procrastinate_worker

echo
printf "Waiting for services to come up"
elapsed=0
failed_service=""
not_ready=1
while [ "$elapsed" -lt "$TIMEOUT_SECONDS" ]; do
    not_ready=0
    for svc in "${LONG_RUNNING_SERVICES[@]}"; do
        if is_failed "$svc"; then
            failed_service="$svc"
            break
        fi
        is_ready "$svc" || not_ready=$((not_ready + 1))
    done
    [ -n "$failed_service" ] && break
    [ "$not_ready" -eq 0 ] && break
    printf "."
    sleep "$POLL_INTERVAL"
    elapsed=$((elapsed + POLL_INTERVAL))
done
echo
echo

echo "--- Stack status ---"
"${DC[@]}" ps --format "table {{.Service}}\t{{.Status}}"
echo

if [ -n "$failed_service" ]; then
    echo "--- '$failed_service' failed to start ---"
    echo "Check its logs: docker compose -f docker/mystic_auth/compose/docker-compose.dev.yml -f docker/app/compose/docker-compose.dev.yml logs $failed_service"
    exit 1
elif [ "$not_ready" -ne 0 ]; then
    echo "--- Timed out after ${TIMEOUT_SECONDS}s waiting for services to become healthy ---"
    echo "Check whichever service above isn't healthy: docker compose -f docker/mystic_auth/compose/docker-compose.dev.yml -f docker/app/compose/docker-compose.dev.yml logs <service>"
    exit 1
fi

if [ "${DEV_UP_TAIL:-1}" = "0" ]; then
    echo "Stack is up (DEV_UP_TAIL=0, skipping log tail). Tail manually with:"
    echo "  docker compose -f docker/mystic_auth/compose/docker-compose.dev.yml -f docker/app/compose/docker-compose.dev.yml logs -f backend frontend procrastinate_worker"
    exit 0
fi

echo "--- Tailing backend + frontend + procrastinate_worker (Ctrl+C stops watching, stack keeps running) ---"
echo "Backend errors/exceptions: http://localhost:8010 (Bugsink)"
echo
exec "${DC[@]}" logs --since "$TAIL_SINCE" -f backend frontend procrastinate_worker
