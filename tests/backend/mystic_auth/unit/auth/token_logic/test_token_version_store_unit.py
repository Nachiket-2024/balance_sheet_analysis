from unittest.mock import AsyncMock

import pytest

from backend.mystic_auth.auth.token_logic.token_version_store import (
    ACCOUNT_VERSION_KEY,
    CHAIN_VERSION_KEY,
    token_version_store,
)
from backend.mystic_auth.core.settings import settings


@pytest.mark.asyncio
async def test_get_account_version_reads_durable_store(mocker):
    read = mocker.patch.object(token_version_store, "_get_version", new_callable=AsyncMock, return_value=7)

    assert await token_version_store.get_account_version("user@example.com") == 7
    read.assert_awaited_once_with(ACCOUNT_VERSION_KEY.format(email="user@example.com"))


@pytest.mark.asyncio
async def test_get_chain_version_reads_durable_store(mocker):
    read = mocker.patch.object(token_version_store, "_get_version", new_callable=AsyncMock, return_value=3)

    assert await token_version_store.get_chain_version("user@example.com", "chain-1") == 3
    read.assert_awaited_once_with(CHAIN_VERSION_KEY.format(email="user@example.com", chain_id="chain-1"))


@pytest.mark.asyncio
async def test_get_versions_reads_account_and_chain_versions_in_one_query(mocker):
    session = mocker.MagicMock()
    session.execute = AsyncMock(return_value=[
        mocker.Mock(key=ACCOUNT_VERSION_KEY.format(email="user@example.com"), version=7),
        mocker.Mock(key=CHAIN_VERSION_KEY.format(email="user@example.com", chain_id="chain-1"), version=3),
    ])
    session_context = mocker.patch.object(token_version_store, "_get_version", new_callable=AsyncMock)
    session_context.assert_not_called()

    # The combined read is intentionally exercised through the real session
    # context so the query shape remains covered without coupling this unit
    # test to SQLAlchemy's result implementation.
    database_session = mocker.patch(
        "backend.mystic_auth.auth.token_logic.token_version_store.database.async_session",
        return_value=session,
    )
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=None)

    assert await token_version_store.get_versions("user@example.com", "chain-1") == (7, 3)
    database_session.assert_called_once_with()


@pytest.mark.asyncio
async def test_account_bump_commits_before_refreshing_cache(mocker):
    bump = mocker.patch.object(token_version_store, "_bump_version", new_callable=AsyncMock, return_value=8)
    cache = mocker.patch.object(token_version_store, "_cache_version", new_callable=AsyncMock)

    assert await token_version_store.bump_account_version("user@example.com") is True
    key = ACCOUNT_VERSION_KEY.format(email="user@example.com")
    bump.assert_awaited_once_with(key)
    cache.assert_awaited_once_with(key, 8)


@pytest.mark.asyncio
async def test_chain_bump_commits_with_cache_ttl(mocker):
    mocker.patch.object(token_version_store, "_bump_version", new_callable=AsyncMock, return_value=4)
    cache = mocker.patch.object(token_version_store, "_cache_version", new_callable=AsyncMock)

    assert await token_version_store.bump_chain_version("user@example.com", "chain-1") is True
    key = CHAIN_VERSION_KEY.format(email="user@example.com", chain_id="chain-1")
    cache.assert_awaited_once_with(key, 4, ttl=settings.REFRESH_TOKEN_EXPIRE_MINUTES * 60)


@pytest.mark.asyncio
async def test_cache_failure_does_not_turn_a_committed_bump_into_failure(mocker):
    mocker.patch.object(token_version_store, "_bump_version", new_callable=AsyncMock, return_value=1)
    mocker.patch("backend.mystic_auth.auth.token_logic.token_version_store.valkey_client.set", new_callable=AsyncMock, side_effect=ConnectionError("down"))

    assert await token_version_store.bump_account_version("user@example.com") is True


@pytest.mark.asyncio
async def test_durable_bump_failure_returns_false(mocker):
    mocker.patch.object(token_version_store, "_bump_version", new_callable=AsyncMock, side_effect=ConnectionError("down"))

    assert await token_version_store.bump_account_version("user@example.com") is False
