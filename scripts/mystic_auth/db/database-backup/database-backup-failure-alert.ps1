param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments = @())
& "$PSScriptRoot/../invoke-bash.ps1" -ScriptPath (Join-Path $PSScriptRoot "database-backup-failure-alert.sh") -Arguments $Arguments
exit $LASTEXITCODE
