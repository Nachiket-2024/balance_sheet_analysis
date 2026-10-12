$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path
& (Join-Path $repoRoot "tests/scripts/mystic_auth/env-tools/test-setup-env.ps1")
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
