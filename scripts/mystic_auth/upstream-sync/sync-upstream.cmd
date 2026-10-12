@echo off
setlocal

rem Command Prompt wrapper for the PowerShell sync-upstream helper.
rem Locates Git Bash and runs the real sync-upstream.sh through it.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0sync-upstream.ps1" %*
exit /b %ERRORLEVEL%
