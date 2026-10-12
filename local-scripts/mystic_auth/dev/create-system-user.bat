@echo off
REM Non-interactively bootstraps the system superuser against the dev stack
REM (docker/mystic_auth/compose/docker-compose.dev.yml). Fill in local-scripts\mystic_auth\dev\system-user.env first.
REM Assumes a fresh account (no existing user with that email): this pipes a
REM fixed 3-line stdin (email, name, password) matching create_system_user.py's
REM "brand new account" prompt sequence. If the account already exists, run
REM `docker compose -f docker/mystic_auth/compose/docker-compose.dev.yml -f docker/app/compose/docker-compose.dev.yml --env-file env/mystic_auth/.env.dev --env-file env/app/.env.dev exec backend python -m mystic_auth.scripts.create_system_user`
REM by hand instead, since that branch asks different questions.
setlocal enabledelayedexpansion
set "SCRIPT_DIR=%~dp0"

for /f "usebackq tokens=1,2 delims==" %%A in (`findstr /v "^#" "%SCRIPT_DIR%system-user.env" ^| findstr /v "^$"`) do (
    set "%%A=%%B"
)

cd /d "%SCRIPT_DIR%..\..\.."

(
  echo %SYSTEM_USER_EMAIL%
  echo %SYSTEM_USER_NAME%
  echo %SYSTEM_USER_PASSWORD%
) | docker compose -f docker/mystic_auth/compose/docker-compose.dev.yml -f docker/app/compose/docker-compose.dev.yml --env-file env/mystic_auth/.env.dev --env-file env/app/.env.dev exec -T backend python -m mystic_auth.scripts.create_system_user

endlocal
