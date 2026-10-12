@echo off
setlocal

rem Command Prompt wrapper for the PowerShell host-run backend helper.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0backend-host-run.ps1" %*
exit /b %ERRORLEVEL%
