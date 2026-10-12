@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0backup-freshness-check.ps1" %*
exit /b %ERRORLEVEL%
