# Non-interactively bootstraps the system superuser against the local-prod
# stack (docker-compose.local-prod.yml). Fill in
# local-scripts/local-prod/system-user.env first. Assumes a fresh account (no
# existing user with that email) : this pipes a fixed 3-line stdin (email,
# name, password) matching create_system_user.py's "brand new account" prompt
# sequence. If the account already exists, run
# `docker compose -f docker-compose.local-prod.yml exec backend python -m mystic_auth.scripts.create_system_user`
# by hand instead, since that branch asks different questions.
$ErrorActionPreference = "Stop"
$repoRoot = Join-Path $PSScriptRoot "../.."
$envFile = Join-Path $PSScriptRoot "system-user.env"
Set-Location $repoRoot

$envValues = @{}
Get-Content $envFile | ForEach-Object {
    if ($_ -match '^\s*#' -or $_ -match '^\s*$') { return }
    $key, $value = $_ -split '=', 2
    $envValues[$key.Trim()] = $value.Trim()
}

$stdin = "$($envValues['SYSTEM_USER_EMAIL'])`n$($envValues['SYSTEM_USER_NAME'])`n$($envValues['SYSTEM_USER_PASSWORD'])`n"

# Piping a string straight into a native exe's stdin via PowerShell's own
# pipeline (`$stdin | docker ...`) makes `docker compose exec` read a leading
# UTF-8 BOM (EF BB BF) that isn't in $stdin at all -- verified by hexdumping
# what the container actually receives. Setting $OutputEncoding does NOT fix
# this. Routing through a temp file + cmd.exe's `<` redirection instead sends
# raw bytes with no BOM, which is what create_system_user.py actually needs :
# a stray U+FEFF would otherwise silently glue itself onto the email.
$tempFile = [System.IO.Path]::GetTempFileName()
try {
    [System.IO.File]::WriteAllText($tempFile, $stdin, (New-Object System.Text.UTF8Encoding $false))
    cmd /c "docker compose -f docker-compose.local-prod.yml exec -T backend python -m mystic_auth.scripts.create_system_user < ""$tempFile"""
} finally {
    Remove-Item $tempFile -ErrorAction SilentlyContinue
}
