@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0backup-upload.ps1" %*
exit /b %ERRORLEVEL%
