# Copies every KEY=VALUE from OldFile into NewFile, for keys present in
# both, skipping a fixed list of fields setup-env.ps1 generates fresh
# (secrets, plus the DB URLs that embed them) and the app name/brand color
# it just prompted for. Also skips any field you listed in
# scripts/app/env-tools/rotate-secrets/fields.env, since a field safe to
# rotate by editing the file is exactly a field that shouldn't be copied
# forward from an old one either - see that file's own header.
#
# Never prints a value, only key names: every line this script writes to
# stdout is safe to appear in an AI coding agent's own tool output/context,
# since the actual secret literals never pass through it. See
# docs/mystic_auth/template-usage/syncing-upstream/agent-prompt.md.
#
# Usage: .\copy-env-values.ps1 OldFile NewFile
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$OldFile,
    [Parameter(Mandatory = $true, Position = 1)]
    [string]$NewFile
)

$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "../../../..")

if (-not (Test-Path $OldFile)) { Write-Error "Not found: $OldFile"; exit 1 }
if (-not (Test-Path $NewFile)) { Write-Error "Not found: $NewFile"; exit 1 }

$ExcludedKeys = @(
    "SECRET_KEY", "BUGSINK_SECRET_KEY", "POSTGRES_PASSWORD", "APP_DB_PASSWORD",
    "BUGSINK_SUPERUSER_PASSWORD", "DATABASE_URL", "APP_DATABASE_URL",
    "APP_NAME", "BRAND_COLOR", "VITE_APP_NAME", "VITE_BRAND_COLOR"
)

$AppFieldsFile = "scripts/app/env-tools/rotate-secrets/fields.env"
if (Test-Path $AppFieldsFile) {
    foreach ($line in Get-Content $AppFieldsFile) {
        if ($line -eq "" -or $line.StartsWith("#") -or -not $line.Contains("=")) {
            continue
        }
        $ExcludedKeys += $line.Substring(0, $line.IndexOf("="))
    }
}

$newContent = Get-Content $NewFile -Raw
$copied = @()
$notInNew = @()
$preservedNewDefaults = @()

foreach ($line in Get-Content $OldFile) {
    $trimmed = $line.Trim()
    if ($trimmed -eq "" -or $trimmed.StartsWith("#") -or -not $trimmed.Contains("=")) {
        continue
    }
    $idx = $trimmed.IndexOf("=")
    $key = $trimmed.Substring(0, $idx)
    $value = $trimmed.Substring($idx + 1)

    if ($ExcludedKeys -contains $key) { continue }

    # Keep a newly introduced production default when the old env file is blank.
    if ($key -eq "BACKUP_UPLOAD_COMMAND" -and $value -eq "") {
        $newLine = Get-Content $NewFile | Where-Object { $_ -match "^$([regex]::Escape($key))=" } | Select-Object -First 1
        if ($null -ne $newLine -and $newLine.Substring($newLine.IndexOf("=") + 1) -ne "") {
            $preservedNewDefaults += $key
            continue
        }
    }

    $pattern = "(?m)^$([regex]::Escape($key))=.*"
    if ($newContent -match $pattern) {
        $safeValue = $value -replace '\$', '$$$$'
        $newContent = [regex]::Replace($newContent, $pattern, "$key=$safeValue")
        $copied += $key
    } else {
        $notInNew += $key
    }
}

Set-Content -Path $NewFile -Value $newContent -NoNewline

$allFields = @($copied) + @($notInNew)

Write-Host "Copied from $OldFile into $NewFile (values not shown):"
Write-Host ""

if ($allFields.Count -eq 0) {
    Write-Host "(nothing to copy)"
} else {
    $fieldWidth = 5
    foreach ($key in $allFields) {
        if ($key.Length -gt $fieldWidth) { $fieldWidth = $key.Length }
    }
    $noWidth = [Math]::Max(3, "$($allFields.Count)".Length)

    "{0,-$noWidth}  {1,-$fieldWidth}  Copied" -f "No.", "Field" | Write-Host
    $n = 0
    foreach ($key in $copied) {
        $n++
        "{0,-$noWidth}  {1,-$fieldWidth}  Yes" -f $n, $key | Write-Host
    }
    foreach ($key in $notInNew) {
        $n++
        "{0,-$noWidth}  {1,-$fieldWidth}  No" -f $n, $key | Write-Host
    }

    Write-Host ""
    Write-Host "$($copied.Count) of $($allFields.Count) field(s) copied."
    if ($notInNew.Count -gt 0) {
        Write-Host "`"No`" means present in $OldFile but not in $NewFile - upstream may have dropped or renamed it, review by hand."
    }
}

Write-Host ""
Write-Host "Not copied on purpose (freshly generated/prompted by setup-env): $($ExcludedKeys -join ' ')"
if ($preservedNewDefaults.Count -gt 0) {
    Write-Host "Preserved non-blank defaults because the old value was blank (review): $($preservedNewDefaults -join ' ')"
}
