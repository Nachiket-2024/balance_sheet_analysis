# tests/backend/conftest.py
#
# Shared fixtures for every real-DB suite under tests/backend/: a real
# PostgreSQL and Valkey, not mocks, since mocking either would hide the kind
# of bug (a Valkey type mismatch, a missed session-revocation call) these
# tests exist to catch.
#
# Lives here rather than per-subdirectory because pytest always collects the
# nearest conftest.py up the tree, so this is the one file every suite is
# guaranteed to load.
import os
import re
from pathlib import Path

# ---------------------------- Environment Setup ----------------------------
# Must run before any `backend.mystic_auth...` import: settings and the
# database/Valkey singletons read the process environment once, at import
# time, and cache it.
#
# If DATABASE_URL / VALKEY_URL are already set (e.g. inside the docker-compose
# network, pointed at the "postgres"/"valkey" service hostnames), leave them
# alone. Otherwise, running from the host, derive a localhost equivalent from
# env/mystic_auth/.env.dev.
_ENV_PATH = Path(__file__).resolve().parents[2] / "env" / "mystic_auth" / ".env.dev"


def _read_env_value(key: str) -> str | None:
    if not _ENV_PATH.exists():
        return None
    for line in _ENV_PATH.read_text().splitlines():
        stripped = line.strip()
        if stripped.startswith(f"{key}=") and not stripped.startswith("#"):
            return stripped.split("=", 1)[1]
    return None


# docker/mystic_auth/compose/docker-compose.dev.yml maps these to non-default
# host ports to avoid colliding with a developer's own local Postgres/Valkey.
# Read the configured mappings so host-run tests follow custom .env overrides.
# Swapping only the hostname and keeping the container's port would silently
# connect to whatever else is listening on the real default port.
_LOCAL_POSTGRES_PORT = _read_env_value("POSTGRES_HOST_PORT") or "5433"
_LOCAL_VALKEY_PORT = _read_env_value("VALKEY_HOST_PORT") or "6380"

if "DATABASE_URL" not in os.environ:
    _docker_db_url = _read_env_value("DATABASE_URL")
    if _docker_db_url:
        os.environ["DATABASE_URL"] = re.sub(
            r"@postgres:\d+", f"@localhost:{_LOCAL_POSTGRES_PORT}", _docker_db_url
        )

# database/connection.py's `database` singleton (the engine every integration
# test hits via the `client` fixture) prefers APP_DATABASE_URL over
# DATABASE_URL (see mystic_auth/core/settings.py's docstring on the least-privilege app DB
# role). .env sets APP_DATABASE_URL too, still pointed at the docker-internal
# "postgres" hostname, so it needs the same localhost rewrite. Without this,
# tests run from the host fail on the first real query with "Temporary
# failure in name resolution" (a request that never touches the DB, like a
# bare 401, would still appear to pass).
if "APP_DATABASE_URL" not in os.environ:
    _docker_app_db_url = _read_env_value("APP_DATABASE_URL")
    if _docker_app_db_url:
        os.environ["APP_DATABASE_URL"] = re.sub(
            r"@postgres:\d+", f"@localhost:{_LOCAL_POSTGRES_PORT}", _docker_app_db_url
        )

if "VALKEY_URL" not in os.environ:
    _docker_valkey_url = _read_env_value("VALKEY_URL")
    if _docker_valkey_url:
        # Use a dedicated logical Valkey DB (15) so test runs never collide
        # with whatever a developer has cached in db 0.
        os.environ["VALKEY_URL"] = re.sub(
            r"(redis://[^@]*@)valkey:\d+/\d+", rf"\1localhost:{_LOCAL_VALKEY_PORT}/15", _docker_valkey_url
        )

# ---------------------------- Dedicated test database ----------------------------
# Redirects DATABASE_URL/APP_DATABASE_URL to a `mystic_auth_test` database on
# the same Postgres server, instead of the real `mystic_auth` one a running
# dev stack's `backend`/`procrastinate_worker` containers use.
#
# Without this, running the suite from a container hits the exact same live
# database a `docker compose up` session's `procrastinate_worker` is
# watching (DATABASE_URL is already set from the container's env_file, so
# the localhost-rewrite above never touches it). Concretely: a deferred job
# gets picked up by the real worker, but before it can mark itself
# "succeeded" in procrastinate_jobs, this file's own
# _procrastinate_app_lifecycle fixture runs its per-test `DELETE FROM
# procrastinate_jobs` teardown, deleting the row the real worker is mid-write
# on ("Job was not found or not in doing/todo status"). A dedicated database
# removes the shared table entirely.
#
# Skipped when CI is set: CI already provisions its own dedicated
# `mystic_auth_ci` Postgres service per run (see ci.yml), and no dev-stack
# container ever runs alongside it.
_BACKEND_DIR = Path(__file__).resolve().parents[2] / "backend"
_TEST_DB_NAME = "mystic_auth_test"


def _with_database(url: str, db_name: str) -> str:
    return re.sub(r"/[^/@]+$", f"/{db_name}", url)


if not os.environ.get("CI"):
    if "DATABASE_URL" in os.environ:
        _original_database_url = os.environ["DATABASE_URL"]
        os.environ["DATABASE_URL"] = _with_database(_original_database_url, _TEST_DB_NAME)
    else:
        _original_database_url = None
    if "APP_DATABASE_URL" in os.environ:
        os.environ["APP_DATABASE_URL"] = _with_database(os.environ["APP_DATABASE_URL"], _TEST_DB_NAME)

    if _original_database_url:
        import subprocess

        import psycopg

        # CREATE DATABASE can't run inside a transaction block, hence
        # autocommit. Connects to the real `mystic_auth` database (known to
        # exist) rather than assuming a "postgres" maintenance database is
        # reachable under this app's own DATABASE_URL role.
        _maintenance_conninfo = _original_database_url.replace("postgresql+asyncpg://", "postgresql://", 1)
        with psycopg.connect(_maintenance_conninfo, autocommit=True) as _conn:
            _exists = _conn.execute(
                "SELECT 1 FROM pg_database WHERE datname = %s", (_TEST_DB_NAME,)
            ).fetchone()
            if not _exists:
                _conn.execute(f'CREATE DATABASE "{_TEST_DB_NAME}"')

        # Migration a4c1e8f2b6d3 already creates Procrastinate's own queue
        # tables/types, so `alembic upgrade head` alone brings a fresh
        # database up to date for both; a separate `procrastinate schema
        # --apply` would error ("type already exists"). Fast once already at
        # head, so this runs unconditionally rather than detecting "already
        # set up".
        _test_env = os.environ.copy()
        subprocess.run(
            ["alembic", "-c", "alembic.ini", "upgrade", "head"],
            cwd=_BACKEND_DIR, env=_test_env, check=True,
        )

# Safety net independent of the dedicated test database above: this suite's
# own worker(s) (audit_log/conftest.py's session-scoped subprocess) now run
# against mystic_auth_test, not the real dev database, so a real dev-stack
# procrastinate_worker no longer shares a queue with these tests at all. This
# still guards the one remaining path a real email could go out: this
# suite's own worker processing a genuinely-deferred send_email_task from a
# signup/password-reset/account-deletion flow. Overrides .env unconditionally
# (unlike DATABASE_URL/VALKEY_URL above, which only fill in a missing value)
# - an explicit `EMAIL_ENABLED=true` already in the environment when pytest
# is invoked still wins.
if "EMAIL_ENABLED" not in os.environ:
    os.environ["EMAIL_ENABLED"] = "false"

# ---------------------------- Imports (after env overrides above) ----------------------------
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from backend.app.main import app
from backend.mystic_auth.database.connection import database
from backend.mystic_auth.procrastinate_tasks.procrastinate_app import (
    app as procrastinate_app,
)
from backend.mystic_auth.valkey.client import valkey_client

# pytest-asyncio hands each test function its own event loop, but
# `database.engine`'s connection pool is a module-level singleton shared
# across the whole run: a pooled asyncpg connection from one test's loop
# isn't safe to reuse from another's ("Future attached to a different
# loop"). NullPool opens a fresh connection per checkout and closes it on
# release instead of pooling it, so no connection survives past the
# request/session that created it.
database.engine = create_async_engine(database.database_url, echo=False, poolclass=NullPool)
database.async_session = sessionmaker(bind=database.engine, class_=AsyncSession, expire_on_commit=False)


# ---------------------------- Valkey isolation ----------------------------
@pytest_asyncio.fixture(autouse=True)
async def _flush_valkey_test_db():
    """Every test starts and ends with an empty Valkey logical DB, so state
    (rate-limit counters, lockouts, single-use tokens) never leaks between
    tests."""
    await valkey_client.flushdb()
    yield
    await valkey_client.flushdb()
    # Same cross-event-loop hazard as the Postgres pool above: drop pooled
    # connections so the next test (a different loop) opens fresh ones.
    await valkey_client.connection_pool.disconnect()


# ---------------------------- Procrastinate connector lifecycle ----------------------------
@pytest_asyncio.fixture(autouse=True)
async def _procrastinate_app_lifecycle():
    """procrastinate_app's PsycopgConnector opens an asyncio-bound connection
    pool: the same per-event-loop hazard as the Postgres/Valkey pools above,
    since a pool opened by one test isn't safe to reuse from another test's
    loop. Opening and closing the connector fresh around every test avoids
    that "Future attached to a different loop" failure.

    Terminal queue rows are pruned on teardown, but `todo`/`doing` rows are
    deliberately left alone until the worker has finished them. Deleting an
    in-flight row races the worker's status update and can lose an audit-log
    job; that was the source of intermittent missing successful
    `users:list_all` entries after a broad integration run."""
    await procrastinate_app.open_async()
    yield
    async with database.async_session() as session:
        await session.execute(
            text("DELETE FROM procrastinate_jobs WHERE status IN ('succeeded', 'failed')")
        )
        await session.commit()
    await procrastinate_app.close_async()


# ---------------------------- HTTP client ----------------------------
@pytest_asyncio.fixture
async def client():
    """An httpx client wired directly to the real ASGI app (no network
    socket), so requests exercise the real routing/middleware/dependency
    stack. base_url uses https:// so the cookie jar honors the Secure
    attribute on the access_token/refresh_token/oauth_state cookies; without
    it httpx silently drops them."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="https://testserver", follow_redirects=False) as ac:
        yield ac


# ---------------------------- Postgres cleanup ----------------------------
@pytest_asyncio.fixture
def created_emails():
    """Tests append every email they create to this list; the fixture
    deletes those rows from the real `users` table on teardown so repeated
    runs against the same database don't accumulate test users."""
    emails: list[str] = []
    yield emails


@pytest_asyncio.fixture(autouse=True)
async def _cleanup_users(created_emails):
    yield
    if not created_emails:
        return
    async with database.async_session() as session:
        await session.execute(text("DELETE FROM users WHERE email = ANY(:emails)"), {"emails": created_emails})
        await session.commit()
