param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments = @())
& "$PSScriptRoot/../invoke-bash.ps1" -ScriptPath (Join-Path $PSScriptRoot "backup-freshness-check.sh") -Arguments $Arguments
exit $LASTEXITCODE
