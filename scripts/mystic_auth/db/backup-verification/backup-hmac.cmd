@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0backup-hmac.ps1" %*
exit /b %ERRORLEVEL%
