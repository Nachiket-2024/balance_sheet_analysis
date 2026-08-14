#!/usr/bin/env bash
# Starts the full stack, waits for long-running services, and prints a
# one-line-per-service status table before tailing focused logs.
#
# Avoids `docker compose up --wait` because alembic and bugsink-seed are
# one-shot containers that should exit 0 after startup work. This polls only
# the long-running services.
#
# On success, tails only backend, frontend, taskiq_worker, and taskiq_scheduler
# logs. That keeps request traffic, Vite output, and async email jobs (plus
# their scheduled retries) visible without Postgres, Redis, Alembic, or
# Bugsink health-check noise. Backend exceptions still go to Bugsink at
# http://localhost:8010.
#
# backend, taskiq_worker, and taskiq_scheduler are restarted after `up -d` so
# their startup banners are fresh even when the stack was already running.
#
# This is the recommended day-to-day command. See README.md. Use plain
# `docker compose up` instead when you actually want every service's full
# logs in one stream (e.g. debugging Postgres/Bugsink/Taskiq startup itself).
#
# Usage: ./scripts/docker/dev-up.sh   (Git Bash or WSL on Windows)
# PowerShell: .\scripts\docker\dev-up.ps1
# Command Prompt: scripts\docker\dev-up.cmd
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

# frontend has no healthcheck in docker-compose.yml, so "Up" is as
# ready as it gets. Every other long-running service does have one.
LONG_RUNNING_SERVICES=(postgres redis bugsink backend taskiq_worker taskiq_scheduler frontend)
TIMEOUT_SECONDS=180
POLL_INTERVAL=2
TAIL_SINCE="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

is_ready() {
    local status
    status="$(docker compose ps --format '{{.Status}}' "$1" 2>/dev/null)"
    case "$status" in
        *"(healthy)"*) return 0 ;;
        "Up "*) [ "$1" = "frontend" ] && return 0 || return 1 ;;
        *) return 1 ;;
    esac
}

is_failed() {
    local status
    status="$(docker compose ps --format '{{.Status}}' "$1" 2>/dev/null)"
    case "$status" in
        *"Exited"*|*"Restarting"*|"") return 0 ;;
        *) return 1 ;;
    esac
}

# --quiet-pull suppresses Compose's repainting pull-progress table. Real pull
# errors still surface through this command's exit code.
docker compose up -d --quiet-pull

# Restart these services so the final tail always includes fresh startup
# banners, even when Compose reused already-running containers.
docker compose restart backend taskiq_worker taskiq_scheduler

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
docker compose ps --format "table {{.Service}}\t{{.Status}}"
echo

if [ -n "$failed_service" ]; then
    echo "--- '$failed_service' failed to start ---"
    echo "Check its logs: docker compose logs $failed_service"
    exit 1
elif [ "$not_ready" -ne 0 ]; then
    echo "--- Timed out after ${TIMEOUT_SECONDS}s waiting for services to become healthy ---"
    echo "Check whichever service above isn't healthy: docker compose logs <service>"
    exit 1
fi

echo "--- Tailing backend + frontend + taskiq_worker + taskiq_scheduler (Ctrl+C stops watching, stack keeps running) ---"
echo "Backend errors/exceptions: http://localhost:8010 (Bugsink)"
echo
exec docker compose logs --since "$TAIL_SINCE" -f backend frontend taskiq_worker taskiq_scheduler
