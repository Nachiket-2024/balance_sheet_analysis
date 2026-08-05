@echo off
setlocal

rem Command Prompt wrapper for the PowerShell backend-exec helper.
rem Usage: scripts\docker\backend-exec.cmd python -m pytest tests/backend/mystic_auth/unit
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0backend-exec.ps1" %*
exit /b %ERRORLEVEL%
