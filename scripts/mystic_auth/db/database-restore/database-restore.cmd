@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0database-restore.ps1" %*
exit /b %ERRORLEVEL%
