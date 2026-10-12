Set-StrictMode -Version Latest
$ErrorActionPreference = "Continue"

# PowerShell counterpart to prod-up.sh. Always passes --env-file
# env/mystic_auth/.env.prod, so this stack never accidentally reads dev's env/mystic_auth/.env.dev.
#
# Usage: .\scripts\mystic_auth\docker\prod\prod-up.ps1 up -d --build
#        .\scripts\mystic_auth\docker\prod\prod-up.ps1 logs -f frontend
# With no arguments, defaults to `up -d --build`.

$RepoRoot = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $PSScriptRoot)))
Set-Location $RepoRoot

$ComposeArgs = if ($args.Count -eq 0) { @("up", "-d", "--build") } else { $args }

& "$RepoRoot/scripts/mystic_auth/env-tools/check-env/check-env.ps1" `
  "env/mystic_auth/.env.prod" `
  "env/app/.env.prod"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

docker compose `
  -f docker/mystic_auth/compose/docker-compose.prod.yml `
  -f docker/app/compose/docker-compose.prod.yml `
  --env-file env/mystic_auth/.env.prod `
  --env-file env/app/.env.prod `
  @ComposeArgs
exit $LASTEXITCODE
