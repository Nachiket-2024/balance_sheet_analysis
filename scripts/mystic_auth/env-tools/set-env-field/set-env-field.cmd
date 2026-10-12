@echo off
setlocal

rem Command Prompt wrapper for the PowerShell env field-setter helper.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0set-env-field.ps1" %*
exit /b %ERRORLEVEL%
