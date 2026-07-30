# tests/backend/conftest.py
#
# Real-dependency fixtures shared by every real-DB test suite under
# tests/backend/ (integration/, security/, performance/): an actual
# PostgreSQL and actual Redis (via `docker compose up -d postgres redis`,
# migrated with `docker compose run --rm alembic`), not mocks. See
# claude.md's Testing sections: security-critical flows must be verified
# against real DB/Redis state, since mocking either one hides exactly the
# kind of bug (e.g. a Redis type mismatch, or a missing session-revocation
# call) these tests exist to catch.
#
# Centralized here (rather than duplicated per subdirectory) specifically
# because of the NullPool reconfiguration below: pytest collects the
# nearest conftest.py up the directory tree regardless of which
# subdirectory is actually invoked (e.g. `pytest tests/backend/security`
# alone never touches tests/backend/integration/), so this fix must live
# somewhere every real-DB suite is guaranteed to import: this file.
import os
import re
from pathlib import Path

# ---------------------------- Environment Setup ----------------------------
# Must run before any `backend.mystic_auth...` import: mystic_auth.core.settings builds its
# Settings() singleton at import time from the process environment, and
# backend.mystic_auth.database.connection / backend.mystic_auth.redis.client build their
# engine/client singletons eagerly at import time too. Both are read once
# and cached for the life of the process.
#
# If DATABASE_URL / REDIS_URL are already set in the environment (e.g. this
# suite is run inside the docker-compose network, where those variables are
# injected as real container env vars pointing at the "postgres"/"redis"
# service hostnames), leave them alone. Otherwise, when running from the host,
# derive a localhost equivalent from the same values already committed in
# .env, so the DB name/credentials never need to be duplicated here.
_ENV_PATH = Path(__file__).resolve().parents[2] / ".env"


def _read_env_value(key: str) -> str | None:
    if not _ENV_PATH.exists():
        return None
    for line in _ENV_PATH.read_text().splitlines():
        stripped = line.strip()
        if stripped.startswith(f"{key}=") and not stripped.startswith("#"):
            return stripped.split("=", 1)[1]
    return None


if "DATABASE_URL" not in os.environ:
    _docker_db_url = _read_env_value("DATABASE_URL")
    if _docker_db_url:
        os.environ["DATABASE_URL"] = _docker_db_url.replace("@postgres:", "@localhost:")

if "REDIS_URL" not in os.environ:
    _docker_redis_url = _read_env_value("REDIS_URL")
    if _docker_redis_url:
        # Use a dedicated logical Redis DB (15) for these test runs so they
        # never collide with whatever a developer has cached in db 0.
        os.environ["REDIS_URL"] = re.sub(
            r"redis://redis:(\d+)/\d+", r"redis://localhost:\1/15", _docker_redis_url
        )

# ---------------------------- Imports (after env overrides above) ----------------------------
import pytest_asyncio  # noqa: E402
from backend.app.main import app  # noqa: E402
from backend.mystic_auth.database.connection import database  # noqa: E402
from backend.mystic_auth.redis.client import redis_client  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import NullPool  # noqa: E402

# pytest-asyncio hands each test function its own event loop, but
# `database.engine`'s connection pool is a module-level singleton shared
# across the whole run: a pooled asyncpg connection opened in one test's
# loop is not safe to reuse from a different test's loop and corrupts
# ("another operation is in progress" / "Future attached to a different
# loop"). NullPool opens a fresh connection per checkout and closes it on
# release instead of returning it to a pool, so no connection ever survives
# past the request/session that created it.
database.engine = create_async_engine(database.database_url, echo=False, poolclass=NullPool)
database.async_session = sessionmaker(bind=database.engine, class_=AsyncSession, expire_on_commit=False)


# ---------------------------- Redis isolation ----------------------------
@pytest_asyncio.fixture(autouse=True)
async def _flush_redis_test_db():
    """Every test starts and ends with an empty Redis logical DB, so state
    (rate-limit counters, lockouts, single-use tokens) from one test can
    never leak into the next."""
    await redis_client.flushdb()
    yield
    await redis_client.flushdb()
    # Same cross-event-loop hazard as the Postgres pool above, but for
    # Redis: drop pooled connections so the next test (a different loop)
    # opens fresh ones instead of reusing ones bound to this loop.
    await redis_client.connection_pool.disconnect()


# ---------------------------- HTTP client ----------------------------
@pytest_asyncio.fixture
async def client():
    """An httpx client wired directly to the real ASGI app (no network
    socket), so requests exercise the actual routing/middleware/dependency
    stack. base_url uses https:// so the client's cookie jar honors the
    Secure attribute on the access_token/refresh_token/oauth_state cookies
    the app sets, otherwise httpx silently drops them."""
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
