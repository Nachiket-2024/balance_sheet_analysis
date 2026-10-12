# Preflight check for a real env/mystic_auth/.env* or env/app/.env* file:
# catches the two mistakes that otherwise only surface as a cryptic
# runtime error, a silently insecure deployment, or Docker's raw "port is
# already allocated" failure.
#
#   1. ERROR (exit 1): ENVIRONMENT=production in this file, but a secret
#      still equals the shipped placeholder from its .example.
#   2. ERROR (exit 1): a real env file is readable by group/other users when
#      PowerShell exposes Unix permission bits. Env files contain signing keys
#      and database credentials and must be owner-only.
#   3. ERROR (exit 1): a Tailscale env file declares TS_CERT_DOMAIN but its
#      public origin/issuer/redirect host does not match that exact DNS name.
#   4. WARNING (exit 0, printed): a <your_...>/<your-domain> placeholder is
#      still present, or a host port this file declares is already bound.
#
# Usage: .\check-env.ps1 [env/mystic_auth/.env.dev ...]
# With no arguments, checks every env/mystic_auth/.env* and env/app/.env*
# file that actually exists.
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Files = @()
)

Set-Location (Join-Path $PSScriptRoot "../../../..")

if ($Files.Count -eq 0) {
    # Globs rather than a fixed list, so a fork's own new mode (e.g. a
    # hand-added env/app/.env.staging) is checked too, with no edit to this
    # upstream-owned script ever required.
    $Files = Get-ChildItem -Path "env/mystic_auth", "env/app" -Filter ".env*" -File -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -notmatch '\.(example|bak|ci-created)$' } |
        ForEach-Object { $_.FullName.Substring((Get-Location).Path.Length + 1) -replace '\\', '/' }
}

if ($Files.Count -eq 0) {
    Write-Error "No env files found to check. Run scripts/mystic_auth/env-tools/setup-env/setup-env.ps1 first."
    exit 1
}

$PlaceholderSecrets = @{
    "SECRET_KEY" = "SECRET_KEY=change_me_in_production_generate_your_own_random_32plus_char_key"
    "BUGSINK_SECRET_KEY" = "BUGSINK_SECRET_KEY=change_me_in_production_generate_your_own_random_50plus_char_key"
    "POSTGRES_PASSWORD" = "POSTGRES_PASSWORD=change_me_in_production"
    "APP_DB_PASSWORD" = "APP_DB_PASSWORD=change_me_in_production"
    "BUGSINK_SUPERUSER_PASSWORD" = "BUGSINK_SUPERUSER_PASSWORD=change_me_in_production"
    "VALKEY_PASSWORD" = "VALKEY_PASSWORD=change_me_in_production"
    "BACKUP_ENCRYPTION_KEY" = "BACKUP_ENCRYPTION_KEY=change_me_in_production"
}

function Test-PortInUse([int]$Port) {
    try {
        $client = New-Object System.Net.Sockets.TcpClient
        $result = $client.BeginConnect("127.0.0.1", $Port, $null, $null)
        $connected = $result.AsyncWaitHandle.WaitOne(200)
        if ($connected -and $client.Connected) {
            $client.EndConnect($result)
            $client.Close()
            return $true
        }
        $client.Close()
        return $false
    } catch {
        return $false
    }
}

function Get-EnvValue([string]$Text, [string]$Name) {
    $line = ($Text -split "`n" | Where-Object { $_ -match "^$Name=" } | Select-Object -First 1)
    if ($null -eq $line) { return '' }
    return ($line -replace "^$Name=", '').Trim()
}

$HasError = $false
$HasWarning = $false

foreach ($f in $Files) {
    if (-not (Test-Path $f)) {
        Write-Host "skip (not found): $f"
        continue
    }

    Write-Host "=== $f ==="
    $content = Get-Content $f -Raw
    $isProd = $content -match '(?m)^ENVIRONMENT=production$'

    # PowerShell 7.3+ exposes Unix mode bits on Linux/macOS. On Windows the
    # ACL model is different and remains the host administrator's responsibility;
    # the shell preflight is authoritative where stat(2) is available.
    if (Get-Command Get-UnixFileMode -ErrorAction SilentlyContinue) {
        $fileMode = Get-UnixFileMode -Path $f
        $forbidden = [System.IO.UnixFileMode]::GroupRead -bor
            [System.IO.UnixFileMode]::GroupWrite -bor
            [System.IO.UnixFileMode]::GroupExecute -bor
            [System.IO.UnixFileMode]::OtherRead -bor
            [System.IO.UnixFileMode]::OtherWrite -bor
            [System.IO.UnixFileMode]::OtherExecute
        $ownerRequired = [System.IO.UnixFileMode]::UserRead -bor [System.IO.UnixFileMode]::UserWrite
        if (($fileMode -band $forbidden) -ne 0 -or ($fileMode -band $ownerRequired) -ne $ownerRequired) {
            Write-Host "  ERROR: env file permissions must be owner read/write only (mode 600 or stricter)."
            $HasError = $true
        }
    }

    $tsCertDomain = Get-EnvValue $content 'TS_CERT_DOMAIN'
    if ($tsCertDomain) {
        $originNames = @('FRONTEND_BASE_URL', 'JWT_ISSUER', 'JWT_AUDIENCE', 'GOOGLE_REDIRECT_URI')
        foreach ($originName in $originNames) {
            $originValue = Get-EnvValue $content $originName
            try { $originHost = ([Uri]$originValue).Host } catch { $originHost = '' }
            if ($originHost -ne $tsCertDomain) {
                Write-Host "  ERROR: $originName host does not match TS_CERT_DOMAIN. Keep all public auth origins on the exact Funnel DNSName."
                $HasError = $true
            }
        }
    }

    if ($isProd) {
        foreach ($key in $PlaceholderSecrets.Keys) {
            $line = $PlaceholderSecrets[$key]
            if (($content -split "`n") -contains $line) {
                Write-Host "  ERROR: $key is still the shipped placeholder, but ENVIRONMENT=production."
                $HasError = $true
            }
        }

        $backupKeyLine = ($content -split "`n" | Where-Object { $_ -match '^BACKUP_ENCRYPTION_KEY=' } | Select-Object -First 1)
        $backupKey = if ($null -ne $backupKeyLine) { $backupKeyLine -replace '^BACKUP_ENCRYPTION_KEY=', '' } else { '' }
        if (-not $backupKeyLine -or -not $backupKey.Trim()) {
            Write-Host "  ERROR: BACKUP_ENCRYPTION_KEY is blank, but ENVIRONMENT=production. Set a high-entropy key before starting backups."
            $HasError = $true
        }

        $backupUploadLine = ($content -split "`n" | Where-Object { $_ -match '^BACKUP_UPLOAD_COMMAND=' } | Select-Object -First 1)
        $backupUpload = if ($null -ne $backupUploadLine) { $backupUploadLine -replace '^BACKUP_UPLOAD_COMMAND=', '' } else { '' }
        if (-not $backupUploadLine -or -not $backupUpload.Trim()) {
            Write-Host "  ERROR: BACKUP_UPLOAD_COMMAND is blank, but ENVIRONMENT=production. Set a command that uploads the encrypted dump and its .hmac sidecar off-host. The command must reference `$DUMP_FILE."
            $HasError = $true
        } elseif ($backupUpload -notmatch 'DUMP_FILE') {
            Write-Host "  ERROR: BACKUP_UPLOAD_COMMAND must reference `$DUMP_FILE so the backup hook uploads the generated dump (and its .hmac sidecar)."
            $HasError = $true
        }
    }

    $placeholderMatches = [regex]::Matches($content, '<your[a-z_-]*>|<your-domain>') |
        ForEach-Object { $_.Value } | Sort-Object -Unique
    if ($placeholderMatches) {
        Write-Host "  WARNING: still has placeholder value(s): $($placeholderMatches -join ' ')"
        $HasWarning = $true
    }

    # A blank or malformed BUGSINK_SUPERUSER_EMAIL isn't just insecure, it's
    # a hard startup failure: Bugsink's own prestart hook rejects it with
    # ValueError and crash-loops, and every service that depends_on bugsink
    # being healthy (alembic, backend, frontend in dev-compose) fails with
    # it - a real live failure mode found running this script's own suite.
    if ($content -match '(?m)^BUGSINK_SUPERUSER_EMAIL=(.*)$') {
        $bugsinkEmail = $Matches[1].Trim()
        if (-not $bugsinkEmail -or $bugsinkEmail -notmatch '^[^@\s]+@[^@\s]+\.[^@\s]+$') {
            Write-Host "  WARNING: BUGSINK_SUPERUSER_EMAIL is blank or not a valid email. Bugsink will crash-loop on startup and take backend/frontend down with it (they depend_on it being healthy). Set it to any valid-looking address, e.g. admin@example.com - it doesn't need to be a real inbox for local dev."
            $HasWarning = $true
        }
    }

    # NGROK_DOMAIN must be a bare domain: the compose file builds the tunnel
    # command as --url=https://${NGROK_DOMAIN}, so a value that already
    # includes a scheme produces a malformed double-scheme URL and ngrok
    # refuses to start (ERR_NGROK_9038) - a hard startup failure, found
    # running this exact mistake against a live tunnel.
    if ($content -match '(?m)^NGROK_DOMAIN=(.*)$') {
        $ngrokDomain = $Matches[1].Trim()
        if ($ngrokDomain -match '://') {
            Write-Host "  ERROR: NGROK_DOMAIN=$ngrokDomain still has a scheme (http:// or https://). It must be the bare domain only, e.g. NGROK_DOMAIN=your-app.ngrok-free.app - ngrok will fail to start with ERR_NGROK_9038 otherwise."
            $HasError = $true
        }
    }

    foreach ($portVar in @("POSTGRES_HOST_PORT", "VALKEY_HOST_PORT", "BACKEND_HOST_PORT", "FRONTEND_HOST_PORT", "BUGSINK_HOST_PORT")) {
        if ($content -match "(?m)^$portVar=(\d+)") {
            $port = [int]$Matches[1]
            if (Test-PortInUse $port) {
                Write-Host "  WARNING: $portVar=$port is already bound by something else on this machine."
                $HasWarning = $true
            }
        }
    }

    if (Test-Path "$f.bak") {
        Write-Host "  WARNING: $f.bak still exists - a leftover plaintext copy of the old secrets. Delete it once you've confirmed $f is correct."
        $HasWarning = $true
    }

    Write-Host ""
}

if ($HasError) {
    Write-Host "Fix the ERROR(s) above before starting this stack. If it's a placeholder secret still set with ENVIRONMENT=production:"
    Write-Host "  scripts/mystic_auth/env-tools/rotate-secrets/rotate-secrets.ps1 (SECRET_KEY/BUGSINK_SECRET_KEY only; see its own header for POSTGRES_PASSWORD/APP_DB_PASSWORD/BUGSINK_SUPERUSER_PASSWORD, which need a live-database step too)"
    exit 1
}

if ($HasWarning) {
    Write-Host "Warnings above won't stop the stack from starting, but review them first."
}

exit 0
