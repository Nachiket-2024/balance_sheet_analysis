param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments = @())
& "$PSScriptRoot/invoke-bash.ps1" -ScriptName "seed-accessibility-user.sh" -Arguments $Arguments
exit $LASTEXITCODE
