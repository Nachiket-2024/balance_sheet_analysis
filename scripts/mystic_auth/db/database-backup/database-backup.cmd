@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0database-backup.ps1" %*
exit /b %ERRORLEVEL%
