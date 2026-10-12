param(
    [Parameter(Mandatory = $true)]
    [string]$ScriptPath,
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Arguments = @()
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Find-GitBash {
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

$bash = Find-GitBash
if (-not $bash) {
    Write-Error "Couldn't find Git Bash. Install Git for Windows or run the .sh script from WSL2/Git Bash."
    exit 1
}

& $bash -l $ScriptPath @Arguments
exit $LASTEXITCODE
