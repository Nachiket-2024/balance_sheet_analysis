@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0seed-accessibility-user.ps1" %*
exit /b %ERRORLEVEL%
