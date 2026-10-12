param(
    [string]$RepoRoot = (Join-Path $PSScriptRoot "../../../..")
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path $RepoRoot).Path
$TempRoot = Join-Path ([System.IO.Path]::GetTempPath()) "mystic-auth-setup-env-$PID"

function Assert-Equal([string]$Expected, [string]$Actual, [string]$Message) {
    if ($Expected -cne $Actual) {
        throw "$Message. Expected '$Expected', got '$Actual'."
    }
}

try {
    New-Item -ItemType Directory -Path $TempRoot -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $TempRoot "env/mystic_auth") -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $TempRoot "env/app") -Force | Out-Null
    Copy-Item (Join-Path $RepoRoot "env/mystic_auth/*.example") (Join-Path $TempRoot "env/mystic_auth")
    Copy-Item (Join-Path $RepoRoot "env/app/*.example") (Join-Path $TempRoot "env/app")
    New-Item -ItemType Directory -Path (Join-Path $TempRoot "frontend") -Force | Out-Null
    Copy-Item (Join-Path $RepoRoot "frontend/.env.example") (Join-Path $TempRoot "frontend/.env.example")
    $SetupScript = Join-Path $TempRoot "scripts/mystic_auth/env-tools/setup-env/setup-env.ps1"
    New-Item -ItemType Directory -Path (Split-Path $SetupScript) -Force | Out-Null
    Copy-Item (Join-Path $RepoRoot "scripts/mystic_auth/env-tools/setup-env/setup-env.ps1") $SetupScript

    # setup-env.ps1 intentionally changes its working directory to the
    # temporary repository copy. Restore the caller's location in a finally
    # block before cleanup, including when setup itself fails.
    $CallerLocation = (Get-Location).Path
    try {
        & $SetupScript -NonInteractive
    }
    finally {
        Set-Location -LiteralPath $CallerLocation
    }

    $MysticAuthFiles = Get-ChildItem (Join-Path $TempRoot "env/mystic_auth") -Filter ".env*.example" |
        ForEach-Object { Join-Path $TempRoot ("env/mystic_auth/" + $_.Name.Substring(0, $_.Name.Length - ".example".Length)) }
    foreach ($File in $MysticAuthFiles) {
        if (-not (Test-Path $File)) { throw "setup-env.ps1 did not create $File" }
        $Brand = (Get-Content $File | Where-Object { $_ -match '^BRAND_COLOR=' }) -replace '^BRAND_COLOR=', ''
        Assert-Equal "#b5533c" $Brand "$File has the wrong BRAND_COLOR"
    }

    $FrontendEnv = Join-Path $TempRoot "frontend/.env"
    $ViteBrand = (Get-Content $FrontendEnv | Where-Object { $_ -match '^VITE_BRAND_COLOR=' }) -replace '^VITE_BRAND_COLOR=', ''
    Assert-Equal "#b5533c" $ViteBrand "frontend/.env has the wrong VITE_BRAND_COLOR"
    Write-Host "PASS: setup-env.ps1 creates canonical default brand colors"
}
finally {
    if (Test-Path $TempRoot) {
        [GC]::Collect()
        [GC]::WaitForPendingFinalizers()
        for ($Attempt = 1; $Attempt -le 5; $Attempt++) {
            try {
                Remove-Item $TempRoot -Recurse -Force -ErrorAction Stop
                break
            }
            catch {
                if ($Attempt -eq 5) { throw }
                Start-Sleep -Milliseconds 200
            }
        }
    }
}
