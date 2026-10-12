@echo off
setlocal

rem Command Prompt wrapper for the PowerShell local-prod-ngrok-up helper.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0local-prod-ngrok-up.ps1" %*
exit /b %ERRORLEVEL%
