@echo off
setlocal

rem Command Prompt wrapper for the PowerShell dev-up helper.
rem Tails backend, frontend, taskiq_worker, and taskiq_scheduler logs via dev-up.ps1.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0dev-up.ps1"
exit /b %ERRORLEVEL%
