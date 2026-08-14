@echo off
REM Non-interactively bootstraps the system superuser against the prod stack
REM (docker-compose.prod.yml). Fill in local-scripts\prod\system-user.env
REM first, with a real production email/password, not the dev placeholder.
REM Assumes a fresh account (no existing user with that email): this pipes a
REM fixed 3-line stdin (email, name, password) matching create_system_user.py's
REM "brand new account" prompt sequence. If the account already exists, run
REM `docker compose -f docker-compose.prod.yml exec backend python -m mystic_auth.scripts.create_system_user`
REM by hand instead, since that branch asks different questions.
setlocal enabledelayedexpansion
set "SCRIPT_DIR=%~dp0"

for /f "usebackq tokens=1,2 delims==" %%A in (`findstr /v "^#" "%SCRIPT_DIR%system-user.env" ^| findstr /v "^$"`) do (
    set "%%A=%%B"
)

cd /d "%SCRIPT_DIR%..\.."

(
  echo %SYSTEM_USER_EMAIL%
  echo %SYSTEM_USER_NAME%
  echo %SYSTEM_USER_PASSWORD%
) | docker compose -f docker-compose.prod.yml exec -T backend python -m mystic_auth.scripts.create_system_user

endlocal
