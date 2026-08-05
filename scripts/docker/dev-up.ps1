Set-StrictMode -Version Latest

# Keep native command stderr non-terminating. Docker Compose writes routine
# progress to stderr on PowerShell 5.1, so failures are checked with
# $LASTEXITCODE after each important command.
$ErrorActionPreference = "Continue"

# Starts the full stack, waits for long-running services, and tails focused
# backend, frontend, and taskiq_worker logs.
#
# Mirrors dev-up.sh for PowerShell users. Avoids `docker compose up --wait`
# because alembic and bugsink-seed are successful one-shot containers.

$RepoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
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

# --quiet-pull suppresses Compose's repainting pull-progress table. Real pull
# errors still surface as a non-zero exit code.
docker compose up -d --quiet-pull
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

# Restart these services so the final tail always includes fresh startup
# banners, even when Compose reused already-running containers.
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
