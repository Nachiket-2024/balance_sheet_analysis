@echo off
REM Non-interactively bootstraps the system superuser against the prod stack
REM (docker/mystic_auth/compose/docker-compose.prod.yml). Fill in
REM local-scripts\mystic_auth\prod\system-user.env first, with a real production
REM email/password, not the dev placeholder. Assumes a fresh account (no
REM existing user with that email): this pipes a fixed 3-line stdin
REM (email, name, password) matching create_system_user.py's "brand new
REM account" prompt sequence. If the account already exists, run
REM `docker compose -f docker/mystic_auth/compose/docker-compose.prod.yml -f docker/app/compose/docker-compose.prod.yml --env-file env/mystic_auth/.env.prod --env-file env/app/.env.prod exec backend python -m mystic_auth.scripts.create_system_user`
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
) | docker compose -f docker/mystic_auth/compose/docker-compose.prod.yml -f docker/app/compose/docker-compose.prod.yml --env-file env/mystic_auth/.env.prod --env-file env/app/.env.prod exec -T backend python -m mystic_auth.scripts.create_system_user

endlocal
