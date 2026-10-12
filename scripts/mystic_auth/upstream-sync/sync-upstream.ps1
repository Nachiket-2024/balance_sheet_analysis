Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# PowerShell/cmd entry point for sync-upstream.sh.
#
# This does NOT reimplement sync-upstream.sh's logic natively. That script is
# dense git plumbing (incremental 3-way apply, a silent-partial-apply guard,
# an executable-bit self-heal, static alembic-head parsing) with its own
# 346-line regression suite (test-sync-upstream.sh) built specifically
# because this class of script is easy to get subtly wrong. A second,
# independently-written implementation would mean two copies of that logic to
# keep in sync forever, with no shared test coverage between them - the
# wrong tradeoff for a script whose entire job is safety nets.
#
# Instead, this locates the Git Bash that already ships with Git for Windows
# (the same `git` install this script needs regardless of shell) and runs
# the real, already-tested sync-upstream.sh through it. One command, no
# manual "open Git Bash first" step, and zero duplicated logic.
#
# Usage: .\scripts\mystic_auth\upstream-sync\sync-upstream.ps1 [upstream-url]

$RepoRoot = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $PSScriptRoot))
Set-Location $RepoRoot
$RealScript = Join-Path $PSScriptRoot "sync-upstream.sh"

function Find-GitBash {
    # Deliberately looks for Git Bash specifically, not just any bash.exe on
    # PATH: on a machine with WSL installed, `C:\Windows\System32\bash.exe`
    # is WSL's own launcher, and handing it $RealScript's Windows-style path
    # would fail (WSL doesn't auto-translate a Windows path passed as an
    # argument the way Git Bash's MSYS runtime does). If you're already
    # inside a WSL/Git Bash prompt, just run sync-upstream.sh directly
    # instead of going through this wrapper.

    # 1. Derive it from wherever `git` itself is installed: Git for Windows
    #    always ships bash.exe at <install-root>\bin\bash.exe, with git.exe
    #    itself either at <install-root>\cmd\git.exe or \mingw64\bin\git.exe.
    $gitCmd = Get-Command git.exe -ErrorAction SilentlyContinue
    if ($gitCmd) {
        $gitDir = Split-Path -Parent $gitCmd.Source
        $installRoot = Split-Path -Parent $gitDir
        $candidate = Join-Path (Join-Path $installRoot "bin") "bash.exe"
        if (Test-Path $candidate) { return $candidate }
    }

    # 2. The two default install locations, in case git.exe resolution above
    #    didn't find anything (e.g. git only reachable via a shim). Either
    #    env var can be unset (e.g. a 32-bit-only Windows install has no
    #    "Program Files (x86)"), so skip a candidate built from an unset one
    #    rather than letting Join-Path fail on a null Path.
    foreach ($base in @($Env:ProgramFiles, ${Env:ProgramFiles(x86)})) {
        if (-not $base) { continue }
        $candidate = Join-Path $base "Git\bin\bash.exe"
        if (Test-Path $candidate) { return $candidate }
    }

    # 3. Last resort: whatever bash.exe is on PATH. Usually Git Bash's own
    #    (if the user added it themselves) - see the WSL caveat above if
    #    this picks up something else instead.
    $onPath = Get-Command bash.exe -ErrorAction SilentlyContinue
    if ($onPath) { return $onPath.Source }

    return $null
}

$BashExe = Find-GitBash
if (-not $BashExe) {
    Write-Host "Couldn't find bash.exe (Git Bash, normally bundled with Git for Windows: https://git-scm.com/download/win)."
    Write-Host "Install Git for Windows, or run this script directly from an existing Git Bash / WSL prompt instead:"
    Write-Host "  ./scripts/mystic_auth/upstream-sync/sync-upstream.sh $($args -join ' ')"
    exit 1
}

# -l (login shell): makes bash re-source its normal profile, so PATH looks
# the same as it would from an interactive Git Bash window - matters here
# since sync-upstream.sh shells out to git/grep/awk/comm itself.
& $BashExe -l $RealScript @args
exit $LASTEXITCODE
