@echo off
setlocal

rem Command Prompt wrapper for the PowerShell env value copy helper.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0copy-env-values.ps1" %*
exit /b %ERRORLEVEL%
