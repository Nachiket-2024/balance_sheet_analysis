param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments = @())
& "$PSScriptRoot/../invoke-bash.ps1" -ScriptPath (Join-Path $PSScriptRoot "database-backup.sh") -Arguments $Arguments
exit $LASTEXITCODE
