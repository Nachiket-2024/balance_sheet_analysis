# Thin, stable entry point - the real targets live in
# makefiles/mystic_auth/make.ps1 (upstream-owned) and makefiles/app/make.ps1
# (yours, ships empty), the same app/mystic_auth split as everything else in
# this repo. This file itself should rarely if ever need to change, so a
# sync almost never touches it. PowerShell ships with every Windows install
# already, so this needs nothing extra - use it in place of `make`, which
# has no built-in Windows version outside WSL/Git Bash. See
# docs/mystic_auth/template-usage/ownership-split.md.
#
# Usage: .\make.ps1 <target>

param(
    [Parameter(Position = 0)]
    [string]$Target = "help"
)

$ErrorActionPreference = "Stop"

. "$PSScriptRoot\makefiles\mystic_auth\make.ps1"

if (Test-Path "$PSScriptRoot\makefiles\app\make.ps1") {
    . "$PSScriptRoot\makefiles\app\make.ps1"
} else {
    $AppTargets = @{}
}

$AllTargets = $MysticAuthTargets.Clone()
foreach ($key in $AppTargets.Keys) {
    $AllTargets[$key] = $AppTargets[$key]
}

if ($AllTargets.ContainsKey($Target)) {
    & $AllTargets[$Target]
} else {
    Write-Error "Unknown target '$Target'. Run '.\make.ps1 help' for the list."
    exit 1
}
