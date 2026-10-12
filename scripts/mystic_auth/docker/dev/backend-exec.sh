#!/usr/bin/env bash
# Thin wrapper around `docker compose exec` for the backend container. Applies
# two workarounds documented in
# docs/mystic_auth/docker/dev-workflow.md#running-a-one-off-command-inside-a-container:
#
#   - MSYS_NO_PATHCONV=1: Git Bash rewrites `-w /repo` into a Windows path
#     before handing it to docker.exe, which then fails with
#     "Cwd must be an absolute path" even though /repo plainly is one.
#   - --user root: pytest.ini writes coverage output to /repo, which is
#     bind-mounted with the host checkout's ownership, not the container's
#     non-root `app` user. Matters on native Linux, harmless elsewhere.
#
# Both are no-ops where they don't apply, so this is safe on every platform.
#
# -w /repo is needed for pytest (pytest.ini's testpaths/--cov paths are
# relative to the repo root), but alembic.ini lives at /repo/backend, not
# /repo, so a bare `alembic heads` from -w /repo fails with "No
# 'script_location' key found in configuration" despite being this
# script's own documented example. ALEMBIC_CONFIG points alembic at the
# right file regardless of cwd, without changing -w for every other
# command (alembic reads this env var itself, no argv rewriting needed).
#
# Usage: scripts/mystic_auth/docker/dev/backend-exec.sh <command> [args...]
#   scripts/mystic_auth/docker/dev/backend-exec.sh python -m pytest tests/backend/mystic_auth/unit
#   scripts/mystic_auth/docker/dev/backend-exec.sh alembic heads
set -euo pipefail

if [ "$#" -eq 0 ]; then
  echo "Usage: scripts/mystic_auth/docker/dev/backend-exec.sh <command> [args...]" >&2
  exit 1
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
cd "$REPO_ROOT"

MSYS_NO_PATHCONV=1 exec docker compose \
  -f docker/mystic_auth/compose/docker-compose.dev.yml \
  -f docker/app/compose/docker-compose.dev.yml \
  --env-file env/mystic_auth/.env.dev \
  --env-file env/app/.env.dev \
  exec --user root -w /repo -e ALEMBIC_CONFIG=/repo/backend/alembic.ini backend "$@"
