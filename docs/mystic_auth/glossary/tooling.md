# Glossary: Local Scripts & Dev Tooling
---

The helper scripts that wrap Docker Compose and other repetitive setup steps for day-to-day development. See [Glossary](README.md) for the full index.

---

## dev-up helper

`scripts/mystic_auth/docker/dev/dev-up.{sh,ps1,cmd}`: starts the dev stack detached, waits for every service's healthcheck, then tails just `backend`/`frontend`/`procrastinate_worker` logs instead of interleaving every container's full boot output (Postgres, Alembic, Bugsink's 100+ migrations, its repeating healthcheck hits, and so on). Plain `docker compose up` still works and is better when you actually need to debug one of those noisier services directly. See [Docker Overview: Day-to-day dev-up helpers](../docker/dev-workflow.md#day-to-day-dev-up-helpers).

---

## backend-exec helper

`scripts/mystic_auth/docker/dev/backend-exec.sh` (and `.ps1`/`.cmd`): runs a one-off command (like `pytest`) inside the running `backend` container, wrapping the `--user root` and path-conversion workarounds that running such a command directly through `docker compose exec` needs on some shells. See [Docker Overview: Running a one-off command inside a container](../docker/dev-workflow.md#running-a-one-off-command-inside-a-container).

---

## non-interactive bootstrap script

A `local-scripts/mystic_auth/<mode>/create-system-user.{sh,ps1,bat}` script that pipes the reserved system account's fresh-creation prompts (email, name, password) from a local `system-user.env` file into the matching upstream Compose file plus the app-owned override for that deployment mode, so you don't have to retype them at an interactive prompt every time you reset a local stack. It only covers fresh-account creation, not promoting an existing account to system. See [System Superuser: Non-interactive bootstrap scripts](../authentication/system-superuser/README.md#non-interactive-bootstrap-scripts).

---

## `create_system_user.py`

The one and only way the reserved system (superuser) account is ever created or granted; there is no API endpoint for either, by design. Run once after the stack is up and migrations have completed. See [System Superuser: Bootstrapping and Promotion](../authentication/system-superuser/README.md).

---

## executable bit

A file-mode flag (`100755` vs `100644`) that git tracks as part of a file itself, separate from a local `chmod`. A `.sh` script committed without it set will keep resetting to non-executable on every clone/pull, even after you `chmod +x` it locally; the fix (`git update-index --chmod=+x <file>`) has to be committed, not just run on disk. See [System Superuser: "Permission denied" running one of these](../authentication/system-superuser/README.md#permission-denied-running-one-of-these).

---

## env file (per-mode)

Each deployment mode (dev, each local-prod tunnel variant, prod) has its own dedicated env template under `env/` (e.g. `env/mystic_auth/.env.dev.example`, `env/mystic_auth/.env.local-prod-ngrok.example`), copied to its real, git-ignored counterpart before first use. This lets every mode hold real values at once without one overwriting another. See [Deployment Guide: Choosing the right env template](../deployment/environment.md#1-choosing-the-right-env-template).

---
