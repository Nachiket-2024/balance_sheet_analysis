Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# Starts only the Docker data services, derives host-reachable connection URLs
# from their configured published ports, runs migrations, and starts Uvicorn
# from the host for debugger-friendly backend development.
#
# Usage: .\scripts\mystic_auth\docker\dev\backend-host-run.ps1 [uvicorn args...]

$RepoRoot = if ($env:BACKEND_HOST_RUN_ROOT) {
    (Resolve-Path $env:BACKEND_HOST_RUN_ROOT).Path
} else {
    Split-Path -Parent (Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $PSScriptRoot)))
}
Set-Location $RepoRoot

$DC = @(
    "-f", "docker/mystic_auth/compose/docker-compose.dev.yml",
    "-f", "docker/app/compose/docker-compose.dev.yml",
    "--env-file", "env/mystic_auth/.env.dev",
    "--env-file", "env/app/.env.dev"
)

function Read-EnvValue([string]$Key) {
    $value = ""
    foreach ($file in @("env/mystic_auth/.env.dev", "env/app/.env.dev")) {
        if (-not (Test-Path $file)) { continue }
        foreach ($line in Get-Content $file) {
            if ($line.StartsWith("$Key=")) { $value = $line.Substring($Key.Length + 1) }
        }
    }
    return $value
}

function Rewrite-HostUrl([string]$Url, [string]$PostgresPort, [string]$ValkeyPort) {
    return $Url -replace "@postgres:\d+", "@localhost:$PostgresPort" `
        -replace "//postgres:\d+/", "//localhost:$PostgresPort/" `
        -replace "@valkey:\d+", "@localhost:$ValkeyPort" `
        -replace "//valkey:\d+/", "//localhost:$ValkeyPort/"
}

$PostgresHostPort = Read-EnvValue "POSTGRES_HOST_PORT"
$ValkeyHostPort = Read-EnvValue "VALKEY_HOST_PORT"
if ([string]::IsNullOrWhiteSpace($PostgresHostPort)) { $PostgresHostPort = "5433" }
if ([string]::IsNullOrWhiteSpace($ValkeyHostPort)) { $ValkeyHostPort = "6380" }

docker compose @DC up -d --wait postgres valkey
$env:DATABASE_URL = Rewrite-HostUrl (Read-EnvValue "DATABASE_URL") $PostgresHostPort $ValkeyHostPort
$env:APP_DATABASE_URL = Rewrite-HostUrl (Read-EnvValue "APP_DATABASE_URL") $PostgresHostPort $ValkeyHostPort
$env:VALKEY_URL = Rewrite-HostUrl (Read-EnvValue "VALKEY_URL") $PostgresHostPort $ValkeyHostPort
$env:ALEMBIC_CONFIG = Join-Path $RepoRoot "backend/alembic.ini"
$PathSeparator = [IO.Path]::PathSeparator
$env:PYTHONPATH = "$RepoRoot/backend" + $(if ($env:PYTHONPATH) { "$PathSeparator$env:PYTHONPATH" } else { "" })

Push-Location backend
try { alembic upgrade head } finally { Pop-Location }
uvicorn app.main:app --reload @args
exit $LASTEXITCODE
