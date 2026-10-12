# Bootstraps every env/mystic_auth/.env* and env/app/.env* file (plus
# frontend/.env) from its .example,
# generating a distinct random value for every secret/password field and
# applying one app name / brand color across all of them, plus Google
# OAuth / Gmail sending credentials if you answer those two optional
# prompts. Never touches a file that already exists - safe to re-run
# after filling in your own per-mode fields (domain, tunnel tokens) by
# hand.
#
# See docs/mystic_auth/template-usage/overview.md for what's still yours to
# fill in after this runs.
param(
    [string]$AppName,
    [string]$BrandColor,
    [switch]$NonInteractive
)

$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "../../../..")

function New-Secret([int]$Length) {
    $bytes = New-Object byte[] ($Length * 2)
    # Windows PowerShell 5.1's .NET Framework does not expose the static
    # RandomNumberGenerator.Fill API that newer PowerShell versions have.
    $generator = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $generator.GetBytes($bytes)
    }
    finally {
        $generator.Dispose()
    }
    $raw = [Convert]::ToBase64String($bytes) -replace '[^A-Za-z0-9]', ''
    return $raw.Substring(0, [Math]::Min($Length, $raw.Length))
}

function Get-EnvValue([string]$File, [string]$Key) {
    if (-not (Test-Path $File)) { return "" }
    $line = Get-Content $File | Where-Object { $_ -match "^$([regex]::Escape($Key))=" } | Select-Object -Last 1
    if ($line) { return $line.Substring($Key.Length + 1) }
    return ""
}

function Get-ConfiguredValue([string]$Key) {
    foreach ($file in @(
        "env/app/.env.dev.bak", "env/mystic_auth/.env.dev.bak",
        "env/app/.env.dev", "env/mystic_auth/.env.dev"
    )) {
        $value = Get-EnvValue $file $Key
        if (-not [string]::IsNullOrWhiteSpace($value)) { return $value }
    }
    return ""
}

$AppNameDefault = Get-ConfiguredValue "APP_NAME"
if ([string]::IsNullOrWhiteSpace($AppNameDefault)) { $AppNameDefault = "MysticAuth" }
$BrandColorDefault = Get-ConfiguredValue "BRAND_COLOR"
if ([string]::IsNullOrWhiteSpace($BrandColorDefault)) { $BrandColorDefault = "#b5533c" }
if (-not $NonInteractive) { $AppName = Read-Host "App name [$AppNameDefault]" }
if ([string]::IsNullOrWhiteSpace($AppName)) { $AppName = $AppNameDefault }
if (-not $NonInteractive) { $BrandColor = Read-Host "Brand color hex [$BrandColorDefault]" }
if ([string]::IsNullOrWhiteSpace($BrandColor)) { $BrandColor = $BrandColorDefault }

# Optional: the two things nothing else in this script can generate for
# you. Skippable (default No) since it's fine to fill these in later by
# hand, or never, if you don't need Google login/outgoing email locally -
# see docs/mystic_auth/template-usage/quickstart.md.
$GoogleClientId = ""
$GoogleClientSecret = ""
$SetupOAuth = if ($NonInteractive) { "" } else { Read-Host "Set up Google OAuth now? [y/N]" }
if ($SetupOAuth -match '^[Yy]') {
    $GoogleClientId = Read-Host "  GOOGLE_CLIENT_ID"
    $GoogleClientSecret = Read-Host "  GOOGLE_CLIENT_SECRET"
}

$FromEmail = ""
$GmailAppPassword = ""
$SetupEmail = if ($NonInteractive) { "" } else { Read-Host "Set up email sending now (Gmail)? [y/N]" }
if ($SetupEmail -match '^[Yy]') {
    $FromEmail = Read-Host "  FROM_EMAIL (Gmail address)"
    $GmailAppPassword = Read-Host "  GMAIL_APP_PASSWORD (from https://myaccount.google.com/apppasswords)"
}

# Auto-discovered by globbing every env/{mystic_auth,app}/.env*.example
# rather than a fixed list, so a fork's own new mode (e.g. a hand-added
# env/app/.env.staging.example) gets bootstrapped too, with no edit to this
# upstream-owned script ever required.
$Pairs = @(
    Get-ChildItem -Path "env/mystic_auth", "env/app" -Filter ".env*.example" -File -ErrorAction SilentlyContinue |
        ForEach-Object {
            $src = $_.FullName.Substring((Get-Location).Path.Length + 1) -replace '\\', '/'
            @{ Src = $src; Dst = $src.Substring(0, $src.Length - ".example".Length) }
        }
)
$Pairs += @{ Src = "frontend/.env.example"; Dst = "frontend/.env" }

$StillNeeded = @()

foreach ($pair in $Pairs) {
    $src = $pair.Src
    $dst = $pair.Dst

    if (-not (Test-Path $src)) { continue }

    if (Test-Path $dst) {
        Write-Host "skip (already exists): $dst"
        continue
    }

    Copy-Item $src $dst
    $content = Get-Content $dst -Raw

    $content = $content -replace '(?m)^APP_NAME=.*', "APP_NAME=$AppName"
    $content = $content -replace '(?m)^BRAND_COLOR=.*', "BRAND_COLOR=$BrandColor"
    $content = $content -replace '(?m)^VITE_APP_NAME=.*', "VITE_APP_NAME=$AppName"
    $content = $content -replace '(?m)^VITE_BRAND_COLOR=.*', "VITE_BRAND_COLOR=$BrandColor"

    # Only if you answered the OAuth/email prompts above - never
    # overwrites with a blank, so an unanswered prompt leaves the shipped
    # placeholder in place for you to fill in by hand later.
    if ($GoogleClientId -and $content -match '(?m)^GOOGLE_CLIENT_ID=') {
        $content = $content -replace '(?m)^GOOGLE_CLIENT_ID=.*', "GOOGLE_CLIENT_ID=$GoogleClientId"
    }
    if ($GoogleClientSecret -and $content -match '(?m)^GOOGLE_CLIENT_SECRET=') {
        $content = $content -replace '(?m)^GOOGLE_CLIENT_SECRET=.*', "GOOGLE_CLIENT_SECRET=$GoogleClientSecret"
    }
    if ($FromEmail -and $content -match '(?m)^FROM_EMAIL=') {
        $content = $content -replace '(?m)^FROM_EMAIL=.*', "FROM_EMAIL=$FromEmail"
    }
    if ($GmailAppPassword -and $content -match '(?m)^GMAIL_APP_PASSWORD=') {
        $content = $content -replace '(?m)^GMAIL_APP_PASSWORD=.*', "GMAIL_APP_PASSWORD=$GmailAppPassword"
    }

    # Distinct generated secrets, only for fields that ship a shared
    # "change_me_in_production..." placeholder. Each variable and each file
    # gets its own independently generated value - a leaked dev secret
    # doesn't compromise prod, and Postgres's superuser password never
    # matches the app role's or Bugsink's.
    if ($content -match '(?m)^POSTGRES_PASSWORD=') {
        $pgPw = New-Secret 24
        $content = $content -replace '(?m)^POSTGRES_PASSWORD=.*', "POSTGRES_PASSWORD=$pgPw"
        $content = $content -replace 'postgres:change_me_in_production@', "postgres:$pgPw@"
    }

    if ($content -match '(?m)^APP_DB_PASSWORD=') {
        $appPw = New-Secret 24
        $content = $content -replace '(?m)^APP_DB_PASSWORD=.*', "APP_DB_PASSWORD=$appPw"
        $content = $content -replace 'mystic_auth_app:change_me_in_production@', "mystic_auth_app:$appPw@"
    }

    $postgresDb = Get-EnvValue $dst "POSTGRES_DB"
    if (-not [string]::IsNullOrWhiteSpace($postgresDb)) {
        $content = [regex]::Replace(
            $content,
            "(?m)^([# ]*(?:DATABASE_URL|APP_DATABASE_URL)=[^/]*/)[^\s#]+",
            "`${1}$postgresDb"
        )
    }

    if ($content -match '(?m)^SECRET_KEY=') {
        $content = $content -replace '(?m)^SECRET_KEY=.*', "SECRET_KEY=$(New-Secret 40)"
    }

    if ($content -match '(?m)^BUGSINK_SECRET_KEY=') {
        $content = $content -replace '(?m)^BUGSINK_SECRET_KEY=.*', "BUGSINK_SECRET_KEY=$(New-Secret 60)"
    }

    if ($content -match '(?m)^BUGSINK_SUPERUSER_PASSWORD=') {
        $content = $content -replace '(?m)^BUGSINK_SUPERUSER_PASSWORD=.*', "BUGSINK_SUPERUSER_PASSWORD=$(New-Secret 24)"
    }

    if ($content -match '(?m)^VALKEY_PASSWORD=') {
        $valkeyPw = New-Secret 32
        $content = $content -replace '(?m)^VALKEY_PASSWORD=.*', "VALKEY_PASSWORD=$valkeyPw"
        if ($content -match '(?m)^VALKEY_URL=') {
            $content = $content -replace '(?m)^VALKEY_URL=.*', "VALKEY_URL=redis://:$valkeyPw@valkey:6379/0"
        }
    }

    if ($content -match '(?m)^BACKUP_ENCRYPTION_KEY=') {
        $content = $content -replace '(?m)^BACKUP_ENCRYPTION_KEY=.*', "BACKUP_ENCRYPTION_KEY=$(New-Secret 64)"
    }

    Set-Content -Path $dst -Value $content -NoNewline
    Write-Host "created: $dst"

    $placeholders = [regex]::Matches($content, '<your[a-z_-]*>|<your-domain>') |
        ForEach-Object { $_.Value } | Sort-Object -Unique
    if ($placeholders) {
        $StillNeeded += "$dst`: $($placeholders -join ' ')"
    }
}

Write-Host ""
Write-Host "Done. Secrets, APP_NAME, and BRAND_COLOR are filled in wherever a new file was created."
if ($StillNeeded.Count -gt 0) {
    Write-Host "Still needs your own values (Google OAuth, SMTP, domain, tunnel tokens):"
    foreach ($line in $StillNeeded) {
        Write-Host "  - $line"
    }
}
Write-Host "See docs/mystic_auth/template-usage/overview.md for OAuth/SMTP/tunnel setup."
