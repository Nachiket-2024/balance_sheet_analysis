#!/usr/bin/env bash
# Starts the full stack and waits for every service to actually report
# healthy/running (docker compose's own --wait, not just "containers
# created") before showing anything else — so a real startup failure fails
# this script instead of silently scrolling past in a wall of logs.
#
# After that, only tails backend + frontend — real request traffic (API
# calls, the frontend dev server's own activity) — never Postgres/Redis/
# Bugsink/Taskiq/Alembic's internals or Bugsink's own health-check polling
# noise (see docs/app/README.md's "Local dev workflow" for why). Backend
# exceptions still go to Bugsink (http://localhost:8010), not this terminal
# — that's what it's for.
#
# Usage: ./scripts/dev-up.sh   (Git Bash on Windows, or any POSIX shell)
set -euo pipefail

docker compose up -d --wait

echo
echo "--- Stack status ---"
docker compose ps --format "table {{.Service}}\t{{.Status}}"
echo

echo "--- Tailing backend + frontend (Ctrl+C stops watching, stack keeps running) ---"
echo "Backend errors/exceptions: http://localhost:8010 (Bugsink)"
echo
docker compose logs -f backend frontend
