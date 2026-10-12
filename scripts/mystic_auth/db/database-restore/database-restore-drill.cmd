@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0database-restore-drill.ps1" %*
exit /b %ERRORLEVEL%
