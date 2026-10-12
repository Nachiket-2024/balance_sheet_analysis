# Troubleshooting: Database Connection Issues

---

## Database connection issues

---

### "Cannot connect to Postgres" from the host, but the container is healthy

The compose file publishes Postgres on host port `5433` (not the default `5432`) specifically to dodge the most common version of this: a native PostgreSQL install, or another Docker Compose project, already listening on `5432`. If you still hit this: e.g. something else is bound to `5433`, or `DATABASE_URL`/`localhost` port was changed: check what's actually listening:

```bash
# Windows: check what's actually listening
netstat -ano | findstr :5433
tasklist /FI "PID eq <pid-from-above>"
```

**Do not stop host services automatically**: this needs an explicit decision from whoever owns that machine (stop the conflicting service, or remap the Docker port again in `docker-compose.dev.yml`). The safe workaround used throughout this project's own test suite: run everything **inside** the Docker network instead of from the host:

```bash
scripts/mystic_auth/docker/dev/backend-exec.sh python -m pytest tests/
```

(`--user root` is needed on native Linux specifically, or pytest-cov's coverage output crashes with a permission error; on Windows with Git Bash, this command needs a separate small workaround too: see [Docker Overview: running a one-off command inside a container](../../docker/dev-workflow.md#running-a-one-off-command-inside-a-container) for both.)

(The `-w /repo` working directory requires the `backend` service's `docker-compose.dev.yml` entry to mount the repo root, not just `./backend`, as an additional volume: see that file's `backend.volumes` for the `.:/repo` line and its comment.)

---

### Migrations won't apply / "relation already exists"

Verify you're pointed at the container you think you are, and that `DATABASE_URL` resolves to the right host (`postgres` inside the Docker network, `localhost` from the host: see any `tests/backend/conftest.py`'s environment-derivation logic for the exact substitution rule). To start completely fresh:

```bash
docker compose -f docker/mystic_auth/compose/docker-compose.dev.yml -f docker/app/compose/docker-compose.dev.yml --env-file env/mystic_auth/.env.dev --env-file env/app/.env.dev exec postgres psql -U ${POSTGRES_USER} -d ${POSTGRES_DB} -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
docker compose -f docker/mystic_auth/compose/docker-compose.dev.yml -f docker/app/compose/docker-compose.dev.yml --env-file env/mystic_auth/.env.dev --env-file env/app/.env.dev run --rm alembic
```

This reproduces the full migration chain from empty state and re-seeds the three baseline policies: verified as part of this project's own Docker/Test Environment Verification pass.

---

### `docker compose exec -it <service>` fails with "Cwd must be an absolute path" or "cannot attach stdin to a TTY"

Two unrelated shell gotchas, both encountered running this project's own test suite from Git Bash on Windows:

- **Path mangling**: Git Bash rewrites absolute-looking paths (`/repo`) to a Windows path (`C:/Program Files/Git/repo`) before they ever reach `docker compose exec`. Fix: prefix the command with `MSYS_NO_PATHCONV=1`.
- **No TTY available**: drop the `-it` flags for any `docker compose exec`/`docker compose run` invoked from a non-interactive shell: `-i`/`-t` require a real terminal, and any script/CI running these commands should omit them entirely (the command runs identically without them; only interactive convenience is lost).

---

See [Troubleshooting](README.md) for the other pages.

---
