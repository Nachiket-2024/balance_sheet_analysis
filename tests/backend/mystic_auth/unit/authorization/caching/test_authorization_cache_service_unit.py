# tests/backend/mystic_auth/unit/authorization/caching/test_authorization_cache_service_unit.py
#
# Unit coverage for AuthorizationCacheService: cache hit/miss behavior,
# invalidation, and the Redis-unavailable fallback. "Fail closed with
# respect to the cache" means never trust
# the cache, always fall through to the database on any doubt).
import json
from unittest.mock import AsyncMock

import pytest
from backend.mystic_auth.authorization.caching.authorization_cache_service import (
    _user_policies_key,
    authorization_cache_service,
)
from backend.mystic_auth.authorization.models.policy_model import Policy

MODULE = "backend.mystic_auth.authorization.caching.authorization_cache_service"


def _policy(name="self_service", actions=None, resource_type="users", conditions=None, is_active=True):
    return Policy(
        name=name,
        description="d",
        actions=actions or ["users:read_own"],
        resource_type=resource_type,
        conditions=conditions,
        is_active=is_active,
    )


# ---------------------------- Cache hit ----------------------------

@pytest.mark.asyncio
async def test_get_user_policies_cache_hit_returns_deserialized_policies(mocker):
    payload = json.dumps([
        {
            "name": "self_service", "description": "d", "actions": ["users:read_own"],
            "resource_type": "users", "conditions": None, "is_active": True,
        }
    ])
    mocker.patch(f"{MODULE}.redis_client.get", new_callable=AsyncMock, return_value=payload)

    result = await authorization_cache_service.get_user_policies("user@example.com")

    assert result is not None
    assert len(result) == 1
    assert result[0].name == "self_service"
    assert result[0].actions == ["users:read_own"]


# ---------------------------- Cache miss ----------------------------

@pytest.mark.asyncio
async def test_get_user_policies_cache_miss_returns_none(mocker):
    mocker.patch(f"{MODULE}.redis_client.get", new_callable=AsyncMock, return_value=None)

    result = await authorization_cache_service.get_user_policies("user@example.com")

    assert result is None


# ---------------------------- Set / round-trip ----------------------------

@pytest.mark.asyncio
async def test_set_user_policies_writes_serialized_payload_with_ttl(mocker):
    set_mock = mocker.patch(f"{MODULE}.redis_client.set", new_callable=AsyncMock)

    await authorization_cache_service.set_user_policies("user@example.com", [_policy()])

    set_mock.assert_awaited_once()
    args, kwargs = set_mock.await_args
    assert args[0] == _user_policies_key("user@example.com")
    stored = json.loads(args[1])
    assert stored[0]["name"] == "self_service"
    assert kwargs["ex"] > 0


# ---------------------------- Invalidate one user ----------------------------

@pytest.mark.asyncio
async def test_invalidate_user_policies_deletes_that_users_key(mocker):
    delete_mock = mocker.patch(f"{MODULE}.redis_client.delete", new_callable=AsyncMock)

    await authorization_cache_service.invalidate_user_policies("user@example.com")

    delete_mock.assert_awaited_once_with(_user_policies_key("user@example.com"))


# ---------------------------- Invalidate all users ----------------------------

@pytest.mark.asyncio
async def test_invalidate_all_user_policies_deletes_every_matching_key(mocker):
    async def _fake_scan_iter(match):
        for key in ["authz:user_policies:a@example.com", "authz:user_policies:b@example.com"]:
            yield key

    mocker.patch(f"{MODULE}.redis_client.scan_iter", side_effect=_fake_scan_iter)
    delete_mock = mocker.patch(f"{MODULE}.redis_client.delete", new_callable=AsyncMock)

    await authorization_cache_service.invalidate_all_user_policies()

    assert delete_mock.await_count == 2


# ---------------------------- Redis-unavailable fallback ----------------------------

@pytest.mark.asyncio
async def test_get_user_policies_falls_back_to_none_when_redis_is_unavailable(mocker):
    mocker.patch(f"{MODULE}.redis_client.get", new_callable=AsyncMock, side_effect=ConnectionError("redis down"))

    result = await authorization_cache_service.get_user_policies("user@example.com")

    assert result is None  # caller treats this exactly like a cache miss -> queries the DB


@pytest.mark.asyncio
async def test_set_user_policies_swallows_redis_errors_without_raising(mocker):
    mocker.patch(f"{MODULE}.redis_client.set", new_callable=AsyncMock, side_effect=ConnectionError("redis down"))

    await authorization_cache_service.set_user_policies("user@example.com", [_policy()])  # must not raise


@pytest.mark.asyncio
async def test_invalidate_user_policies_swallows_redis_errors_without_raising(mocker):
    mocker.patch(f"{MODULE}.redis_client.delete", new_callable=AsyncMock, side_effect=ConnectionError("redis down"))

    await authorization_cache_service.invalidate_user_policies("user@example.com")  # must not raise


@pytest.mark.asyncio
async def test_get_user_policies_corrupt_payload_returns_none_not_a_crash(mocker):
    mocker.patch(f"{MODULE}.redis_client.get", new_callable=AsyncMock, return_value="not-valid-json{{{")

    result = await authorization_cache_service.get_user_policies("user@example.com")

    assert result is None
