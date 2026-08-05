#!/usr/bin/env bash
# Thin wrapper around `docker compose exec` for the backend container. It
# applies the two Windows/Git Bash workarounds documented in
# docs/mystic_auth/docker/overview.md#running-a-one-off-command-inside-a-container:
#
#   - MSYS_NO_PATHCONV=1: Git Bash rewrites `-w /repo` into a Windows path
#     before handing it to docker.exe, which then fails with
#     "Cwd must be an absolute path" even though /repo plainly is one.
#   - --user root: pytest.ini writes coverage output to /repo, which is
#     bind-mounted with the host checkout's ownership, not the container's
#     non-root `app` user. This matters on native Linux and is harmless elsewhere.
#
# Both are no-ops where they do not apply, so this wrapper is safe to use on
# every platform.
#
# Usage: scripts/docker/backend-exec.sh <command> [args...]
#   scripts/docker/backend-exec.sh python -m pytest tests/backend/mystic_auth/unit
#   scripts/docker/backend-exec.sh alembic heads
set -euo pipefail

if [ "$#" -eq 0 ]; then
  echo "Usage: scripts/docker/backend-exec.sh <command> [args...]" >&2
  exit 1
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

MSYS_NO_PATHCONV=1 exec docker compose exec --user root -w /repo backend "$@"
