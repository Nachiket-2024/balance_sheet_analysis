# Sets one or more fields across every real env file that already declares
# each key, leaving every other field untouched. For a value that's the
# same everywhere on purpose (SUPPORT_EMAIL, GOOGLE_CLIENT_ID,
# ...), instead of opening and editing five files by
# hand, one field at a time.
#
# Two ways to use it:
#
#   From a file (no arguments, easiest): copy shared-values.env.example
#   (next to this script) to shared-values.env, fill in whichever fields
#   you want set everywhere with a normal text editor, then run:
#
#     .\set-env-field.ps1
#
#   For a field you added yourself (one only env/app/ declares), use the
#   parallel scripts/app/env-tools/set-env-field/shared-values.env.example
#   instead - same copy/fill/run steps, ships empty, upstream never edits
#   it. Both files are read in this mode; the app one wins on overlap.
#
#   Direct (one-line, scriptable - what docs/agent prompts use):
#
#     .\set-env-field.ps1 KEY1=VALUE1 [KEY2=VALUE2 ...] [file ...]
#
# Any argument containing "=" is a field assignment (only the first "="
# splits key from value). Any argument without "=" is a target file. With
# no file arguments, targets every env/mystic_auth/.env* and env/app/.env*
# file plus frontend/.env that actually exists. A file missing a given key
# is skipped for that field, not created or appended to.
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Args = @()
)

$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "../../../..")

$Assignments = [ordered]@{}
$Files = @()

if ($Args.Count -eq 0) {
    $ValuesFile = Join-Path $PSScriptRoot "shared-values.env"
    $AppValuesFile = "scripts/app/env-tools/set-env-field/shared-values.env"
    if (-not (Test-Path $ValuesFile) -and -not (Test-Path $AppValuesFile)) {
        Write-Error "No shared-values.env found. Copy scripts/mystic_auth/env-tools/set-env-field/shared-values.env.example to scripts/mystic_auth/env-tools/set-env-field/shared-values.env (template fields) and/or scripts/app/env-tools/set-env-field/shared-values.env.example to scripts/app/env-tools/set-env-field/shared-values.env (your own fields), fill in the fields you want set everywhere, then run this again."
        exit 1
    }

    # Read mystic_auth's file first, then app's - app wins on overlap, same
    # convention as env_file ordering elsewhere in this template.
    foreach ($valuesFile in @($ValuesFile, $AppValuesFile)) {
        if (-not (Test-Path $valuesFile)) { continue }
        foreach ($line in Get-Content $valuesFile) {
            if ($line -eq "" -or $line.StartsWith("#") -or -not $line.Contains("=")) {
                continue
            }
            $idx = $line.IndexOf("=")
            $key = $line.Substring(0, $idx)
            $value = $line.Substring($idx + 1)
            if ($value -eq "") { continue }
            $Assignments[$key] = $value
        }
    }

    if ($Assignments.Count -eq 0) {
        Write-Error "Neither shared-values.env has any fields filled in. Edit one, then run this again."
        exit 1
    }
} else {
    foreach ($arg in $Args) {
        $idx = $arg.IndexOf("=")
        if ($idx -ge 0) {
            $key = $arg.Substring(0, $idx)
            $value = $arg.Substring($idx + 1)
            if ($key -notmatch '^[A-Z_][A-Z0-9_]*$') {
                Write-Error "'$key' doesn't look like an env var name (uppercase letters, digits, underscores)."
                exit 1
            }
            $Assignments[$key] = $value
        } else {
            $Files += $arg
        }
    }

    if ($Assignments.Count -eq 0) {
        Write-Error "No KEY=VALUE arguments given."
        exit 1
    }
}

if ($Files.Count -eq 0) {
    # Globs rather than a fixed list, so a fork's own new mode (e.g. a
    # hand-added env/app/.env.staging) is targeted too, with no edit to this
    # upstream-owned script ever required.
    $Files = Get-ChildItem -Path "env/mystic_auth", "env/app" -Filter ".env*" -File -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -notmatch '\.(example|bak|ci-created)$' } |
        ForEach-Object { $_.FullName.Substring((Get-Location).Path.Length + 1) -replace '\\', '/' }
    if (Test-Path "frontend/.env") { $Files += "frontend/.env" }
}

if ($Files.Count -eq 0) {
    Write-Error "No env files found. Run scripts/mystic_auth/env-tools/setup-env/setup-env.ps1 first."
    exit 1
}

$SetIn = @{}
$MissingFiles = @()

foreach ($f in $Files) {
    if (-not (Test-Path $f)) {
        $MissingFiles += $f
        continue
    }

    $content = Get-Content $f -Raw

    foreach ($key in $Assignments.Keys) {
        $pattern = "(?m)^$([regex]::Escape($key))=.*"
        if ($content -match $pattern) {
            $safeValue = $Assignments[$key] -replace '\$', '$$$$'
            $content = [regex]::Replace($content, $pattern, "$key=$safeValue")
            $SetIn[$key] = $true
        }
    }

    Set-Content -Path $f -Value $content -NoNewline
}

if ($MissingFiles.Count -gt 0) {
    Write-Host "Not found, skipped: $($MissingFiles -join ' ')"
    Write-Host ""
}

# Column widths: widest key name (or the "Field" header, whichever is
# longer) and enough digits for the row count, so the table lines up the
# same regardless of how long an individual field name is.
$KeyList = @($Assignments.Keys)
$FieldWidth = 5
foreach ($key in $KeyList) {
    if ($key.Length -gt $FieldWidth) { $FieldWidth = $key.Length }
}
$NoWidth = [Math]::Max(3, "$($KeyList.Count)".Length)

"{0,-$NoWidth}  {1,-$FieldWidth}  Updated" -f "No.", "Field" | Write-Host

$UpdatedCount = 0
for ($i = 0; $i -lt $KeyList.Count; $i++) {
    $key = $KeyList[$i]
    if ($SetIn.ContainsKey($key)) {
        $UpdatedCount++
        "{0,-$NoWidth}  {1,-$FieldWidth}  Yes" -f ($i + 1), $key | Write-Host
    } else {
        "{0,-$NoWidth}  {1,-$FieldWidth}  No" -f ($i + 1), $key | Write-Host
    }
}

Write-Host ""
Write-Host "$UpdatedCount of $($KeyList.Count) field(s) updated."

if ($UpdatedCount -eq 0) {
    Write-Error "No target file declares any of: $($KeyList -join ', ')"
    exit 1
}
