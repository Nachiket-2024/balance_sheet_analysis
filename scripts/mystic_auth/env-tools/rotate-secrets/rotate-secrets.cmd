@echo off
setlocal

rem Command Prompt wrapper for the PowerShell secret rotation helper.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0rotate-secrets.ps1" %*
exit /b %ERRORLEVEL%
