# tests/backend/mystic_auth/unit/database/test_connection_unit.py
#
# Database is a module-level singleton built once at import time; this
# guards its actual engine/session configuration (URL, pool settings,
# expire_on_commit), since nothing else in the suite asserts on it, and a
# regression here (e.g. losing pool_pre_ping) would only surface as an
# intermittent "connection already closed" under real production load, not
# as a test failure anywhere else.
#
# Pool/session assertions below construct a fresh Database(...) rather than
# inspecting the global `database` singleton's own .engine/.async_session:
# tests/backend/conftest.py deliberately reassigns those two attributes on
# the shared singleton to a NullPool engine for the whole test session (see
# its own comment), so asserting on the singleton here would really be
# asserting on conftest's override, not on Database's own default behavior.
import pytest
from backend.mystic_auth.core.settings import settings
from backend.mystic_auth.database.connection import Database, database
from sqlalchemy.ext.asyncio import AsyncSession


def test_database_engine_is_configured_from_settings_database_url():
    fresh = Database(settings.DATABASE_URL)

    # str(engine.url) masks the password (SQLAlchemy's own repr behavior);
    # compare the pieces that are actually visible instead of the raw URL.
    assert fresh.engine.url.drivername == "postgresql+asyncpg"
    assert fresh.engine.url.database == settings.DATABASE_URL.rsplit("/", 1)[-1].split("?")[0]


def test_database_engine_has_pre_ping_enabled_by_default():
    # Without this, a pooled connection that went stale (DB restart, network
    # blip, idle firewall timeout) surfaces as a request-time
    # OperationalError instead of being silently replaced.
    fresh = Database(settings.DATABASE_URL)

    assert fresh.engine.pool._pre_ping is True


def test_database_engine_recycles_connections_before_common_idle_timeouts_by_default():
    # 1800s (30 min), below most default DB/proxy idle-connection timeouts.
    fresh = Database(settings.DATABASE_URL)

    assert fresh.engine.pool._recycle == 1800


def test_async_session_is_bound_to_its_own_engine_with_expire_on_commit_disabled():
    # expire_on_commit=False: attributes on a committed object stay readable
    # without triggering an implicit re-query, needed since sessions here
    # are frequently read from after commit within the same request.
    fresh = Database(settings.DATABASE_URL)

    assert fresh.async_session.kw["bind"] is fresh.engine
    assert fresh.async_session.kw["expire_on_commit"] is False


@pytest.mark.asyncio
async def test_get_session_yields_a_usable_async_session_and_closes_it_after():
    # Uses the real, shared `database` singleton (the same one every
    # request-scoped FastAPI dependency actually gets), not a fresh
    # instance: this is exercising get_session's generator behavior, which
    # conftest's pool override doesn't change.
    session_generator = database.get_session()
    session = await anext(session_generator)

    assert isinstance(session, AsyncSession)
    assert not session.in_transaction()

    # The generator's `async with` block exits (and closes the session)
    # once nothing more is asked of it, exactly like FastAPI's own
    # dependency-injection teardown.
    with pytest.raises(StopAsyncIteration):
        await anext(session_generator)


def test_database_constructor_accepts_an_arbitrary_url_independent_of_the_singleton():
    # Confirms Database is a reusable class (not incidentally singleton-only
    # behavior): the module-level `database` above is itself just one
    # instance of it, constructed from settings.DATABASE_URL.
    custom = Database("postgresql+asyncpg://user:pass@otherhost:5432/otherdb")

    assert custom.engine.url.host == "otherhost"
    assert custom.engine.url.database == "otherdb"
    assert custom is not database
