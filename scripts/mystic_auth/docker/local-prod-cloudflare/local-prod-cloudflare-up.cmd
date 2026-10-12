@echo off
setlocal

rem Command Prompt wrapper for the PowerShell local-prod-cloudflare-up helper.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0local-prod-cloudflare-up.ps1" %*
exit /b %ERRORLEVEL%
