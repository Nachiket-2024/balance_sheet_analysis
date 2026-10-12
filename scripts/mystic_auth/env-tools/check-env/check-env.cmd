@echo off
setlocal

rem Command Prompt wrapper for the PowerShell env preflight checker.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0check-env.ps1" %*
exit /b %ERRORLEVEL%
