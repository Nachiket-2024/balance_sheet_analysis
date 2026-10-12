Set-StrictMode -Version Latest
$ErrorActionPreference = "Continue"

# PowerShell counterpart to backend-exec.sh. See that file for why
# --user root is here. It fixes native Linux coverage-output ownership and is
# a no-op on Windows/Docker Desktop. PowerShell and Command Prompt were never
# affected by the Git-Bash-only `-w /repo` path-rewriting bug. See
# docs/mystic_auth/docker/dev-workflow.md#running-a-one-off-command-inside-a-container),
# so there's no MSYS_NO_PATHCONV equivalent needed here.
#
# Usage: .\scripts\mystic_auth\docker\dev\backend-exec.ps1 python -m pytest tests/backend/mystic_auth/unit
#        .\scripts\mystic_auth\docker\dev\backend-exec.ps1 alembic heads
#
# -w /repo is needed for pytest (pytest.ini's testpaths/--cov paths are
# relative to the repo root), but alembic.ini lives at /repo/backend, not
# /repo, so a bare `alembic heads` from -w /repo fails with "No
# 'script_location' key found in configuration" despite being this
# script's own documented example above. ALEMBIC_CONFIG points alembic at
# the right file regardless of cwd, without changing -w for every other
# command.

if ($args.Count -eq 0) {
    Write-Error "Usage: scripts\mystic_auth\docker\dev\backend-exec.ps1 <command> [args...]"
    exit 1
}

$RepoRoot = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $PSScriptRoot)))
Set-Location $RepoRoot

docker compose `
  -f docker/mystic_auth/compose/docker-compose.dev.yml `
  -f docker/app/compose/docker-compose.dev.yml `
  --env-file env/mystic_auth/.env.dev `
  --env-file env/app/.env.dev `
  exec --user root -w /repo -e ALEMBIC_CONFIG=/repo/backend/alembic.ini backend @args
exit $LASTEXITCODE
