Set-StrictMode -Version Latest

# Deliberately NOT $ErrorActionPreference = "Stop": docker compose (build
# progress, pull progress, etc.) routinely writes routine, non-error output
# to stderr. PowerShell 5.1 wraps every stderr line from a native command
# into a terminating ErrorRecord when ErrorActionPreference is "Stop", which
# killed this script immediately after the first `docker compose up -d`
# line, before it ever reached the final `docker compose logs -f` tail :
# so the taskiq_worker startup lines (and everything else) never appeared.
# Native command failures are instead caught explicitly via $LASTEXITCODE
# checks below, same as the existing check after `docker compose up -d`.
$ErrorActionPreference = "Continue"

# Starts the full stack and waits for every long-running service to report
# healthy, or just running for the frontend dev server, before tailing the
# backend/frontend/taskiq_worker logs.
#
# This mirrors dev-up.sh for PowerShell users. It does not use
# `docker compose up --wait` because alembic and bugsink-seed are one-shot
# containers that should exit 0 after successful startup work.

$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$LongRunningServices = @(
    "postgres",
    "redis",
    "bugsink",
    "backend",
    "taskiq_worker",
    "frontend"
)
$TimeoutSeconds = 180
$PollIntervalSeconds = 2
$TailSince = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")

function Get-ServiceStatus {
    param([Parameter(Mandatory = $true)][string]$Service)

    $status = docker compose ps --format "{{.Status}}" $Service 2>$null
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

docker compose up -d
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

# backend/taskiq_worker are the two services whose boot banner (Uvicorn's
# "Application startup complete", Taskiq's "Listening started", etc.) is
# actually useful to see. `docker compose up -d` leaves an already-running
# container alone when nothing about it changed, so on a rerun against a
# live stack those banners are from whenever it originally booted : older
# than $TailSince below, so the tail at the bottom would silently skip
# them. Restarting the two here guarantees a fresh banner inside the
# --since window on every run, not just the first.
docker compose restart backend taskiq_worker
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
docker compose ps --format "table {{.Service}}`t{{.Status}}"
Write-Host ""

if ($failedService -ne "") {
    Write-Host "--- '$failedService' failed to start ---"
    Write-Host "Check its logs: docker compose logs $failedService"
    exit 1
}
if ($notReady -ne 0) {
    Write-Host "--- Timed out after ${TimeoutSeconds}s waiting for services to become healthy ---"
    Write-Host "Check whichever service above isn't healthy: docker compose logs <service>"
    exit 1
}

Write-Host "--- Tailing backend + frontend + taskiq_worker (Ctrl+C stops watching, stack keeps running) ---"
Write-Host "Backend errors/exceptions: http://localhost:8010 (Bugsink)"
Write-Host ""
docker compose logs --since $TailSince -f backend frontend taskiq_worker
exit $LASTEXITCODE
