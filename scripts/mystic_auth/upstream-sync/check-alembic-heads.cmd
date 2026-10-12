@echo off
setlocal

rem Command Prompt wrapper for the PowerShell check-alembic-heads helper.
rem Locates Git Bash and runs the real check-alembic-heads.sh through it.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0check-alembic-heads.ps1" %*
exit /b %ERRORLEVEL%
