@echo off
setlocal

rem Command Prompt wrapper for the PowerShell env setup helper.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup-env.ps1"
exit /b %ERRORLEVEL%
