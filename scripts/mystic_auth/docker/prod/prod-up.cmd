@echo off
setlocal

rem Command Prompt wrapper for the PowerShell prod-up helper.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0prod-up.ps1" %*
exit /b %ERRORLEVEL%
