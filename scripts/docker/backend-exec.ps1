Set-StrictMode -Version Latest
$ErrorActionPreference = "Continue"

# PowerShell counterpart to backend-exec.sh. See that file for why
# --user root is here. It fixes native Linux coverage-output ownership and is
# a no-op on Windows/Docker Desktop. PowerShell and Command Prompt were never
# affected by the Git-Bash-only `-w /repo` path-rewriting bug. See
# docs/mystic_auth/docker/overview.md#running-a-one-off-command-inside-a-container),
# so there's no MSYS_NO_PATHCONV equivalent needed here.
#
# Usage: .\scripts\docker\backend-exec.ps1 python -m pytest tests/backend/mystic_auth/unit
#        .\scripts\docker\backend-exec.ps1 alembic heads

if ($args.Count -eq 0) {
    Write-Error "Usage: scripts\docker\backend-exec.ps1 <command> [args...]"
    exit 1
}

$RepoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $RepoRoot

docker compose exec --user root -w /repo backend @args
exit $LASTEXITCODE
