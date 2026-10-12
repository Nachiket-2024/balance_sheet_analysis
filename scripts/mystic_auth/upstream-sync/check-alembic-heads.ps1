Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# PowerShell/cmd entry point for check-alembic-heads.sh. Same "locate Git
# Bash, run the real script through it" approach as sync-upstream.ps1 - see
# that file's header comment for why this isn't a native reimplementation.
#
# Usage: .\scripts\mystic_auth\upstream-sync\check-alembic-heads.ps1

$RepoRoot = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $PSScriptRoot))
Set-Location $RepoRoot
$RealScript = Join-Path $PSScriptRoot "check-alembic-heads.sh"

function Find-GitBash {
    # See sync-upstream.ps1's Find-GitBash for the full rationale (in
    # particular, why this deliberately doesn't just take the first
    # bash.exe found on PATH).
    $gitCmd = Get-Command git.exe -ErrorAction SilentlyContinue
    if ($gitCmd) {
        $gitDir = Split-Path -Parent $gitCmd.Source
        $installRoot = Split-Path -Parent $gitDir
        $candidate = Join-Path (Join-Path $installRoot "bin") "bash.exe"
        if (Test-Path $candidate) { return $candidate }
    }

    foreach ($base in @($Env:ProgramFiles, ${Env:ProgramFiles(x86)})) {
        if (-not $base) { continue }
        $candidate = Join-Path $base "Git\bin\bash.exe"
        if (Test-Path $candidate) { return $candidate }
    }

    $onPath = Get-Command bash.exe -ErrorAction SilentlyContinue
    if ($onPath) { return $onPath.Source }

    return $null
}

$BashExe = Find-GitBash
if (-not $BashExe) {
    Write-Host "Couldn't find bash.exe (Git Bash, normally bundled with Git for Windows: https://git-scm.com/download/win)."
    Write-Host "Install Git for Windows, or run this script directly from an existing Git Bash / WSL prompt instead:"
    Write-Host "  ./scripts/mystic_auth/upstream-sync/check-alembic-heads.sh"
    exit 1
}

& $BashExe -l $RealScript @args
exit $LASTEXITCODE
