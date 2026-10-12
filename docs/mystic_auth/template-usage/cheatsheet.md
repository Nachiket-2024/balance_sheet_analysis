# Command Cheat Sheet

---

*Part of [Using This Repository as a Template](overview.md). One-line "when to run this" for every script in the template, so you don't have to re-read each one's own doc page to remember what it's for. Each command shown is the `.sh` (Git Bash/WSL/Linux/macOS) form; swap `.sh` for `.ps1` (PowerShell) or `.cmd` (Command Prompt) - same arguments, same behavior. A `make` (or, on native Windows, `make.ps1`) target exists for the most common ones too - see [Makefile shortcuts](#makefile-shortcuts) below.*

## Day one

| Command | When to run it |
|---|---|
| `./scripts/mystic_auth/env-tools/quickstart/quickstart.sh` | Fresh clone, want a working login in one command. See [Quickstart](quickstart.md). |
| `./scripts/mystic_auth/env-tools/setup-env/setup-env.sh` | Just the env-file bootstrap step, without bringing the stack up. Prompts for app name, brand color, and optionally Google OAuth/Gmail credentials. Safe to re-run, skips files that already exist. |
| `./scripts/mystic_auth/docker/dev/dev-up.sh` | Bring the dev stack up (or back up after a reboot). Waits for every service to become healthy, then tails `backend`/`frontend`/`procrastinate_worker` logs. |
| `./scripts/mystic_auth/docker/dev/backend-host-run.sh` | Optional backend debugging path: keep Postgres/Valkey in Docker, derive their host URLs from the configured multi-project port mappings, run migrations, and run FastAPI on the host with reload. |

## Day two and after

| Command | When to run it |
|---|---|
| `./scripts/mystic_auth/env-tools/check-env/check-env.sh` | Before starting any mode, dev included. Fails if a secret is still the shipped placeholder under `ENVIRONMENT=production`, or if production backup encryption/upload configuration is incomplete (`BACKUP_UPLOAD_COMMAND` must reference `$DUMP_FILE`); warns on remaining `<your_...>` placeholders, a host port already in use, or a blank/invalid `BUGSINK_SUPERUSER_EMAIL` (which crash-loops Bugsink and takes backend/frontend down with it). |
| `./scripts/mystic_auth/env-tools/set-env-field/set-env-field.sh` | You need to change one value (a contact address, a shared rate limit) across every env file at once, instead of opening five files by hand. |
| `./scripts/mystic_auth/env-tools/rotate-secrets/rotate-secrets.sh` | Rotate `SECRET_KEY`/`BUGSINK_SECRET_KEY` (or your own `env/app/` fields listed in a copied `scripts/app/env-tools/rotate-secrets/fields.env.example`) in an existing env file. Logs everyone out; see the script's own header for what it deliberately does *not* rotate. |
| `./scripts/mystic_auth/env-tools/copy-env-values/copy-env-values.sh OLD NEW` | Carrying real values (OAuth secret, SMTP password) from an old env file into a freshly regenerated one, without ever printing them. |
| `docker compose -f docker/mystic_auth/compose/docker-compose.dev.yml -f docker/app/compose/docker-compose.dev.yml --env-file env/mystic_auth/.env.dev --env-file env/app/.env.dev exec -it backend python -m mystic_auth.scripts.create_system_user` | One-time: bootstrap or promote the reserved system superuser account. See [System Superuser](../authentication/system-superuser/README.md). |
| `./scripts/mystic_auth/docker/dev/backend-exec.sh <command>` | Run a one-off command inside the running `backend` container (tests, `alembic heads`, a shell), with the Windows/Linux path-handling workarounds already applied. |
| `./scripts/mystic_auth/db/database-backup/database-backup.sh [compose-file]` | Dump the app database and the Bugsink database to timestamped `.dump` files under `backups/`. |
| `./scripts/mystic_auth/db/backup-verification/backup-freshness-check.sh [backup-dir] [max-age-hours]` | Fail if the required database backups are missing, empty, or older than the configured age. |
| `./scripts/mystic_auth/db/database-restore/database-restore.sh <backup-file> [compose-file]` | Restore a `.dump`/`.sql` backup. Destructive: asks for confirmation unless you pass `-y`. |

## Deploying

| Command | When to run it |
|---|---|
| `./scripts/mystic_auth/docker/prod/prod-up.sh` | Bring up `docker-compose.prod.yml` (self-hosted, Caddy-managed TLS). Forwards all arguments, so `prod-up.sh logs -f frontend` etc. also works. |
| `./scripts/mystic_auth/docker/local-prod-cloudflare/local-prod-cloudflare-up.sh` | Production-shaped stack behind a free Cloudflare Quick/Named Tunnel, for testing prod locally without your own public IP. |
| `./scripts/mystic_auth/docker/local-prod-ngrok/local-prod-ngrok-up.sh` | Same, behind an ngrok tunnel. |
| `./scripts/mystic_auth/docker/local-prod-tailscale/local-prod-tailscale-up.sh` | Same, behind Tailscale Funnel. See [Local-Prod: which tunnel do I want?](../deployment/local-prod/README.md#which-tunnel-do-i-want) to pick one. |

## Staying in sync with upstream

| Command | When to run it |
|---|---|
| `./scripts/mystic_auth/upstream-sync/sync-upstream.sh` | Pull in fixes/features from the original template. See [Staying in Sync with Upstream](syncing-upstream/README.md) for the full walkthrough. |
| `./scripts/mystic_auth/upstream-sync/check-alembic-heads.sh` | After a sync, check whether it and your own project each added a migration on the same fork point (two heads). Run automatically as part of `sync-upstream.sh`; standalone here for re-checking without a full sync. |

## Verifying your own changes to this template's tooling

*Only relevant if you're modifying `scripts/mystic_auth/` itself - upstream maintenance, not day-to-day template use.*

| Command | When to run it |
|---|---|
| `tests/scripts/mystic_auth/env-tools/test-env-tooling.sh` | After touching any `env-tools/` script. Regression suite against a throwaway copy of `env/`, never touches your real files. Runs in CI too. |
| `tests/scripts/mystic_auth/upstream-sync/test-sync-upstream.sh` | After touching `sync-upstream.sh`. Regression suite against throwaway fake repos. Runs in CI too. |
| `tests/scripts/mystic_auth/lint/check-script-paths.sh` | After any rename/restructure. Checks every CI, script, and doc path reference actually resolves. Runs through `ci/mystic_auth/tooling.sh` in CI too. |
| `tests/scripts/mystic_auth/lint/check-split-paths.sh` | After any rename/restructure. Checks for a stale pre-split `docker/`/`env/`/`scripts/` path reference (one that's missing its `mystic_auth/`/`app/` segment) anywhere in source, scripts, or docs. Runs in CI too. |
| `tests/scripts/mystic_auth/lint/check-image-digests.sh` | After pinning or updating any `@sha256:...` image digest in a compose file. Checks every pinned digest is a syntactically valid 64-character sha256. Runs in CI too. |

## Makefile shortcuts

If you have `make` installed (already the case on most Linux/macOS setups, and inside WSL/Git Bash), the root `Makefile` wraps the most common commands above so you don't need to remember the full path or which platform script to use:

```bash
make dev              # ./scripts/mystic_auth/docker/dev/dev-up.sh
make quickstart       # ./scripts/mystic_auth/env-tools/quickstart/quickstart.sh
make setup-env        # ./scripts/mystic_auth/env-tools/setup-env/setup-env.sh
make check-env        # ./scripts/mystic_auth/env-tools/check-env/check-env.sh
make superuser        # create/promote the system superuser
make sync             # ./scripts/mystic_auth/upstream-sync/sync-upstream.sh
make help             # list every target
```

This is purely a convenience layer: everything it runs is one of the commands above, unchanged.

**On native Windows (PowerShell, no WSL/Git Bash) without `make`**, `make` itself doesn't ship with Windows at all, unlike on Linux/macOS where it's either preinstalled or one package-manager command away. Rather than asking you to install a new tool just for this, use the root `make.ps1` instead: the same targets, ships with every Windows install already (no extra install), just swap `make` for `.\make.ps1`:

```powershell
.\make.ps1 dev
.\make.ps1 quickstart
.\make.ps1 help
```

A few targets (`test-tooling`, `test-sync`, `test-backup-freshness`, `lint-paths`, `lint-split`, `backup`, `backup-freshness`) are regression suites and database scripts that only exist as `.sh` files, since they're POSIX-oriented tooling; `make.ps1` shells out to `bash` for those (Git for Windows already provides it if you cloned this repo with Git in the first place). Every other target runs natively in PowerShell, no `bash` needed.

Neither `make` nor PowerShell required at all? Use the `.sh`/`.ps1`/`.cmd` commands directly instead - nothing here requires either wrapper.

Want your own target (a `deploy-staging`, a `lint`)? Add it to `makefiles/app/Makefile` (and/or `makefiles/app/make.ps1`'s `$AppTargets` hashtable) instead of editing the root `Makefile`/`make.ps1` - those files ship empty and upstream never touches them again, so your target survives every future `sync-upstream.sh` run untouched. See [The `app/` + `mystic_auth/` Split](ownership-split.md).

---

See [Using This Repository as a Template](overview.md) for the rest: quickstart in full, the ownership split, building on the template, and deployment.

---
