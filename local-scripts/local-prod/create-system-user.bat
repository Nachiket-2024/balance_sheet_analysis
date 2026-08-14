@echo off
REM Non-interactively bootstraps the system superuser against the local-prod
REM stack (docker-compose.local-prod.yml). Fill in
REM local-scripts\local-prod\system-user.env first. Assumes a fresh account
REM (no existing user with that email): this pipes a fixed 3-line stdin
REM (email, name, password) matching create_system_user.py's "brand new
REM account" prompt sequence. If the account already exists, run
REM `docker compose -f docker-compose.local-prod.yml exec backend python -m mystic_auth.scripts.create_system_user`
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
) | docker compose -f docker-compose.local-prod.yml exec -T backend python -m mystic_auth.scripts.create_system_user

endlocal
