@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0database-backup-failure-alert.ps1" %*
exit /b %ERRORLEVEL%
