# CI/CD Overview

## Workflow

`.github/workflows/ci.yml` triggers on every push and pull request targeting
`main`. It declares top-level `permissions: contents: read` because none of the
jobs push commits, comment on PRs, or need write access. A compromised action
dependency in this workflow can only read the checkout.

There are five independent jobs. The first four run on every push and PR. The
fifth runs only on a push to `main`.

```mermaid
flowchart LR
    Trigger(["Push / PR to main"])
    TriggerMain(["Push to main only"])

    Trigger --> Backend["backend<br/><small>lint, type-check, bandit,<br/>pip-audit, pytest (85% cov gate)</small>"]
    Trigger --> Frontend["frontend<br/><small>typecheck, lint,<br/>test:coverage, build</small>"]
    Trigger --> Secrets["secrets-scan<br/><small>gitleaks, full git history</small>"]
    Trigger --> DockerBuild["docker-build<br/><small>build both images, assert no leaked logs,<br/>boot the dev stack, smoke-test it</small>"]
    TriggerMain --> DockerFullSuite["docker-full-suite<br/><small>full backend + frontend suites,<br/>run inside the actual containers</small>"]
```

### `backend`: Backend (unit + integration)

- Spins up Postgres 15 and Redis 7 as GitHub Actions service containers. Compose
  remains the source of truth for local development, but service containers are
  a lower-overhead CI equivalent for the backend job.
- Provides all required settings as job-level environment variables with
  clearly fake CI-only values because CI has no checked-in `.env`. `APP_NAME`
  is set to `MysticAuth` only because `Settings` requires a value. It is a test
  placeholder, not branding that a downstream project must keep in sync.
- Installs `backend/requirements.txt` and `backend/requirements-dev.txt`, then
  runs `pip-audit -r backend/requirements.txt`.
- Runs `ruff check`, `mypy`, and `bandit -c pyproject.toml` as separate steps so
  the failing tool is obvious in the Actions UI.
- Runs `alembic upgrade head`, then `alembic check`. The check fails if models
  drift from what the migrations create.
- Runs backend unit, integration, and security suites. The integration and
  security steps use `--cov-append`, so the final 85% gate checks cumulative
  coverage across all three suites. `pytest.ini` intentionally does not set
  `--cov-fail-under` because that would break partial local runs. See
  [Testing Overview](../testing/overview.md).
- Runs `pytest tests/backend/mystic_auth/performance` as a non-blocking step
  because timing thresholds can be noisy on shared GitHub-hosted runners.

### `frontend`: Frontend (typecheck + lint + test + build)

- Node is pinned to `22.22.0` because React Router 8 requires Node
  `>=22.22.0`.
- Runs `npm ci --legacy-peer-deps`, `npm audit --audit-level=high`,
  `npm run typecheck`, `npm run lint`, `npm run test:coverage`, and
  `npm run build` as separate steps. `test:coverage` is used instead of plain
  `test` so `vitest.config.ts` coverage thresholds are enforced.

### `secrets-scan`: Secrets scan (gitleaks)

- Checks out full git history with `fetch-depth: 0` and runs
  [gitleaks](https://github.com/gitleaks/gitleaks). This catches secrets that
  were committed and later removed from the working tree.

### `docker-build`: Docker image build verification

- Builds `docker/backend.Dockerfile` and `docker/frontend.Dockerfile --target production` to confirm both images still build cleanly.
- Validates all three Compose files parse: `docker-compose.yml`, `docker-compose.local-prod.yml`, and `docker-compose.prod.yml`.
- Runs the built backend image and asserts `/app/logs` exists but is **empty**: a regression guard for a real bug found during a pre-release image-contents audit (local access-log files, with real request data, were previously getting baked into the image via a `.dockerignore` gap: see [Security Decisions](../security/decisions.md#dockerignore-previously-let-local-files-leak-into-built-images)). The directory itself is expected to exist (the app creates it on import); this only checks that no host-side log content rode along inside it.
- Boots the real dev stack with `docker compose up -d --build postgres redis
  alembic backend frontend`, waits for `/health/ready` and the frontend dev
  server, checks response bodies, and tears the stack down. This verifies the
  images and Compose wiring actually serve traffic. It does not re-run the test
  suite because that is handled by `docker-full-suite`.
- Blanks `BUGSINK_SUPERUSER_EMAIL` in the job's temporary `.env` copy before
  booting because `bugsink` and `bugsink-seed` are not started in this job. This
  avoids waiting for a DSN file that will never be written.
- Prints `docker compose logs --no-color` on failure so container startup
  failures have useful context in the Actions UI.
- Does not push images or deploy. That is an explicit template scope boundary,
  not an oversight.

### `docker-full-suite`: Full test suite via Docker (main only)

- Gated to `if: github.event_name == 'push' && github.ref == 'refs/heads/main'`.
  It does not run on pull requests.
- Boots the backend stack with the same `BUGSINK_SUPERUSER_EMAIL` override as
  `docker-build`, then runs the same unit, integration, and security tiers
  inside the running backend container. `--user root` is required because
  coverage output writes to `/repo`, the whole-repo bind mount. Native Linux
  does not let the container's non-root `app` user write there. See
  [Docker Overview: running a one-off command inside a container](../docker/overview.md#running-a-one-off-command-inside-a-container).
- Boots the frontend, then runs its full test suite inside that container the same way.
- Same on-failure `docker compose logs` step as `docker-build`.
- This repeats tests already run natively. The value is running them through the
  deployable image, real container filesystem, installed dependencies, and
  Compose networking. It is `main`-only to avoid doubling PR CI time for the
  same source code.

---

## What's covered

- Backend unit/integration/security suites, against real Postgres/Redis, gated by an 85% cumulative-coverage threshold; performance tests run too, non-blocking.
- Backend lint (ruff), type-checking (mypy), and security scanning (bandit): all configured in `backend/pyproject.toml`.
- A model/migration drift check (`alembic check`): fails if a SQLAlchemy model's columns or indexes don't match what the checked-in migrations actually produce.
- Full frontend type-check, lint, test (with coverage thresholds enforced), and production build.
- Both Docker images still build, and (on every PR) the actual dev compose stack boots and serves traffic.
- On every push to `main`: the entire backend + frontend test suites, re-run a second time inside the real containers rather than a bare runner.
- Dependency vulnerability scanning on every push/PR: `pip-audit` (backend, blocking) and `npm audit --audit-level=high` (frontend, blocking). There is no scheduled/automated dependency-update bot in this repo; dependency bumps are a manual, deliberate action (see the header comment in `backend/requirements.txt`), not something that opens PRs on its own.
- Secret scanning across full git history (`gitleaks`), independent of the backend/frontend jobs.

---

## What's not covered (tracked, not silently missing)

See [Concerns](../concerns/README.md) for the full entries:

- No image push to a registry and no deployment stage: deploying is a manual, documented process (see [Deployment Guide](../deployment/guide.md)), not automated.

This is deliberately left as a documented gap rather than added: extending `ci.yml` with a deploy stage is a workflow change with its own blast radius (new required checks, new secrets, a specific hosting target to assume), and unnecessary cloud-specific tooling doesn't belong in a template repository with no assumed production target.

---

## Local equivalents

Everything CI runs can be run locally:

```bash
# Backend static analysis (from repo root; dev tools installed via requirements-dev.txt)
# ruff's import-sorting/per-file-ignore rules are path-relative to its own
# working directory, not to --config's location, so this one still needs a
# `cd`: kept a single self-contained line so it doesn't change your shell's
# directory afterward.
(cd backend && ruff check app mystic_auth alembic ../tests/backend)
mypy --config-file backend/pyproject.toml backend/app backend/mystic_auth
bandit -r backend/app backend/mystic_auth -c backend/pyproject.toml
alembic -c backend/alembic.ini check

# Backend tests (from repo root, against local or Dockerized Postgres/Redis)
python -m pytest tests/backend/app tests/backend/mystic_auth/unit tests/backend/mystic_auth/integration tests/backend/mystic_auth/security -q
python -m pytest tests/backend/mystic_auth/performance -q

# Frontend (from repo root)
npm run typecheck --prefix frontend && npm run lint --prefix frontend && npm run test:coverage --prefix frontend && npm run build --prefix frontend

# Secrets scan (from repo root; requires gitleaks installed, or run via Docker)
gitleaks detect --source . -v

# Docker image builds (from repo root)
docker build -f docker/backend.Dockerfile -t backend:local .
docker build --target production -f docker/frontend.Dockerfile -t frontend:local .

# Boot + smoke-test the dev stack, the same thing docker-build does on every PR
cp .env.example .env
sed -i 's/^BUGSINK_SUPERUSER_EMAIL=.*/BUGSINK_SUPERUSER_EMAIL=/' .env   # skip the wasted Bugsink-DSN wait: bugsink isn't started below
docker compose up -d --build postgres redis alembic backend frontend
curl -sf http://localhost:8000/health/ready   # wait/retry until it returns {"status":"ok"}
curl -sf http://localhost:5173                # wait/retry until it responds
docker compose down -v && rm .env

# Full suite through the actual containers, the same thing docker-full-suite
# does on every push to main
cp .env.example .env
sed -i 's/^BUGSINK_SUPERUSER_EMAIL=.*/BUGSINK_SUPERUSER_EMAIL=/' .env
docker compose up -d --build postgres redis alembic backend
# --user root: needed on native Linux, or pytest-cov's coverage output
# (written to /repo, the whole-repo bind mount) crashes with a permission
# error: see docs/mystic_auth/docker/overview.md's "running a one-off
# command inside a container" section
docker compose exec -T --user root backend bash -c "
  cd /repo &&
  python -m pytest tests/backend/app tests/backend/mystic_auth/unit -q &&
  python -m pytest tests/backend/mystic_auth/integration -q --cov-append &&
  python -m pytest tests/backend/mystic_auth/security -q --cov-append --cov-fail-under=85
"
docker compose up -d --build frontend
docker compose exec -T frontend sh -c "npm run test -- --run"
docker compose down -v && rm .env
```
