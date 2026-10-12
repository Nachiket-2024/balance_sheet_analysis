@echo off
setlocal

rem Command Prompt wrapper for the PowerShell quickstart helper.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0quickstart.ps1"
exit /b %ERRORLEVEL%
