param(
    [Parameter(Mandatory = $true)]
    [string]$ScriptName,
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Arguments = @()
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$gitCmd = Get-Command git.exe -ErrorAction SilentlyContinue
$bash = $null
if ($gitCmd) {
    $gitDir = Split-Path -Parent $gitCmd.Source
    $candidate = Join-Path (Join-Path (Split-Path -Parent $gitDir) "bin") "bash.exe"
    if (Test-Path $candidate) { $bash = $candidate }
}
if (-not $bash) {
    foreach ($base in @($Env:ProgramFiles, ${Env:ProgramFiles(x86)})) {
        if (-not $base) { continue }
        $candidate = Join-Path $base "Git\bin\bash.exe"
        if (Test-Path $candidate) { $bash = $candidate; break }
    }
}
if (-not $bash) {
    $onPath = Get-Command bash.exe -ErrorAction SilentlyContinue
    if ($onPath) { $bash = $onPath.Source }
}
if (-not $bash) {
    Write-Error "Couldn't find Git Bash. Install Git for Windows or run the .sh script from WSL2/Git Bash."
    exit 1
}

& $bash -l (Join-Path $PSScriptRoot $ScriptName) @Arguments
exit $LASTEXITCODE
