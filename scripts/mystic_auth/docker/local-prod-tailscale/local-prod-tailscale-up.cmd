@echo off
setlocal

rem Command Prompt wrapper for the PowerShell local-prod-tailscale-up helper.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0local-prod-tailscale-up.ps1" %*
exit /b %ERRORLEVEL%
