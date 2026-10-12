Set-StrictMode -Version Latest

# Keep native command stderr non-terminating. Docker Compose writes routine
# progress to stderr on PowerShell 5.1, so failures are checked with
# $LASTEXITCODE after each important command.
$ErrorActionPreference = "Continue"

# Starts the full stack, waits for long-running services, and tails focused
# backend, frontend, and procrastinate_worker logs.
#
# Mirrors dev-up.sh for PowerShell users. Avoids `docker compose up --wait`
# because alembic and bugsink-seed are successful one-shot containers.

$RepoRoot = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $PSScriptRoot)))
Set-Location $RepoRoot

# Compose files/env files live under docker/ and env/, so every invocation
# below needs the flags explicitly. Two -f/--env-file pairs: mystic_auth
# (the template) plus app (yours, ships empty).
$DC = @(
    "-f", "docker/mystic_auth/compose/docker-compose.dev.yml",
    "-f", "docker/app/compose/docker-compose.dev.yml",
    "--env-file", "env/mystic_auth/.env.dev",
    "--env-file", "env/app/.env.dev"
)

$LongRunningServices = @(
    "postgres",
    "valkey",
    "bugsink",
    "backend",
    "procrastinate_worker",
    "frontend"
)

# GeoIP is opt-in. When the dev env requests it, include the Compose profile
# automatically so the updater provisions the shared database before login
# tests; a configured path without the profile would leave readiness unhealthy.
$GeoIpConfigured = Get-Content "env/mystic_auth/.env.dev" | Where-Object {
    $_ -match '^GEOIP_DB_PATH=.+$'
} | Select-Object -First 1
if ($null -ne $GeoIpConfigured) {
    $GeoIpAccount = Get-Content "env/mystic_auth/.env.dev" | Where-Object {
        $_ -match '^GEOIPUPDATE_ACCOUNT_ID=.+$'
    } | Select-Object -First 1
    $GeoIpLicense = Get-Content "env/mystic_auth/.env.dev" | Where-Object {
        $_ -match '^GEOIPUPDATE_LICENSE_KEY=.+$'
    } | Select-Object -First 1
    if ($null -eq $GeoIpAccount -or $null -eq $GeoIpLicense) {
        Write-Error "GEOIP_DB_PATH is set in env/mystic_auth/.env.dev, but GEOIPUPDATE_ACCOUNT_ID and GEOIPUPDATE_LICENSE_KEY are both required for the GeoIP updater. Set both MaxMind credentials or clear GEOIP_DB_PATH before running dev-up.ps1."
        exit 1
    }
    $DC += "--profile"
    $DC += "geoip"
    $LongRunningServices += "geoipupdate"
}
$TimeoutSeconds = 180
$PollIntervalSeconds = 2
$TailSince = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")

function Get-ServiceStatus {
    param([Parameter(Mandatory = $true)][string]$Service)

    $status = docker compose @DC ps --format "{{.Status}}" $Service 2>$null
    if ($LASTEXITCODE -ne 0 -or $null -eq $status) {
        return ""
    }
    return ($status -join "`n").Trim()
}

function Test-ServiceReady {
    param([Parameter(Mandatory = $true)][string]$Service)

    $status = Get-ServiceStatus -Service $Service
    if ($status.Contains("(healthy)")) {
        return $true
    }
    if ($Service -eq "frontend" -and $status.StartsWith("Up ")) {
        return $true
    }
    return $false
}

function Test-ServiceFailed {
    param([Parameter(Mandatory = $true)][string]$Service)

    $status = Get-ServiceStatus -Service $Service
    return ($status -eq "" -or $status.Contains("Exited") -or $status.Contains("Restarting"))
}

# --quiet-pull suppresses Compose's repainting pull-progress table. Real pull
# errors still surface as a non-zero exit code.
docker compose @DC up -d --quiet-pull
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

# Restart these services so the final tail always includes fresh startup
# banners, even when Compose reused already-running containers.
docker compose @DC restart backend procrastinate_worker
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

Write-Host ""
Write-Host -NoNewline "Waiting for services to come up"

$elapsed = 0
$failedService = ""
$notReady = 1

while ($elapsed -lt $TimeoutSeconds) {
    $notReady = 0

    foreach ($service in $LongRunningServices) {
        if (Test-ServiceFailed -Service $service) {
            $failedService = $service
            break
        }
        if (-not (Test-ServiceReady -Service $service)) {
            $notReady += 1
        }
    }

    if ($failedService -ne "" -or $notReady -eq 0) {
        break
    }

    Write-Host -NoNewline "."
    Start-Sleep -Seconds $PollIntervalSeconds
    $elapsed += $PollIntervalSeconds
}

Write-Host ""
Write-Host ""
Write-Host "--- Stack status ---"
docker compose @DC ps --format "table {{.Service}}`t{{.Status}}"
Write-Host ""

if ($failedService -ne "") {
    Write-Host "--- '$failedService' failed to start ---"
    Write-Host "Check its logs: docker compose -f docker/mystic_auth/compose/docker-compose.dev.yml -f docker/app/compose/docker-compose.dev.yml logs $failedService"
    exit 1
}
if ($notReady -ne 0) {
    Write-Host "--- Timed out after ${TimeoutSeconds}s waiting for services to become healthy ---"
    Write-Host "Check whichever service above isn't healthy: docker compose -f docker/mystic_auth/compose/docker-compose.dev.yml -f docker/app/compose/docker-compose.dev.yml logs <service>"
    exit 1
}

if ($env:DEV_UP_TAIL -eq "0") {
    Write-Host "Stack is up (DEV_UP_TAIL=0, skipping log tail). Tail manually with:"
    Write-Host "  docker compose -f docker/mystic_auth/compose/docker-compose.dev.yml -f docker/app/compose/docker-compose.dev.yml logs -f backend frontend procrastinate_worker"
    exit 0
}

Write-Host "--- Tailing backend + frontend + procrastinate_worker (Ctrl+C stops watching, stack keeps running) ---"
Write-Host "Backend errors/exceptions: http://localhost:8010 (Bugsink)"
Write-Host ""
docker compose @DC logs --since $TailSince -f backend frontend procrastinate_worker
exit $LASTEXITCODE
