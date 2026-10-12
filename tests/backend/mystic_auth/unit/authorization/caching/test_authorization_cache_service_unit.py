# Unit coverage for AuthorizationCacheService: cache hit/miss, invalidation, and the
# Valkey-unavailable fallback (on any doubt, skip the cache and hit the database).
import json
from unittest.mock import AsyncMock

import pytest

from backend.mystic_auth.authorization.caching.authorization_cache_service import (
    _user_permissions_key,
    _user_policies_key,
    authorization_cache_service,
)
from backend.mystic_auth.authorization.models.policy_model import Policy
from backend.mystic_auth.authorization.models.user_permission_model import (
    UserPermission,
)

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


def _grant(action="users:read_own", resource_type="users", conditions=None, is_active=True):
    return UserPermission(
        action=action,
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
    mocker.patch(f"{MODULE}.valkey_client.get", new_callable=AsyncMock, return_value=payload)

    result = await authorization_cache_service.get_user_policies("user@example.com")

    assert result is not None
    assert len(result) == 1
    assert result[0].name == "self_service"
    assert result[0].actions == ["users:read_own"]


# ---------------------------- Cache miss ----------------------------

@pytest.mark.asyncio
async def test_get_user_policies_cache_miss_returns_none(mocker):
    mocker.patch(f"{MODULE}.valkey_client.get", new_callable=AsyncMock, return_value=None)

    result = await authorization_cache_service.get_user_policies("user@example.com")

    assert result is None


# ---------------------------- Set / round-trip ----------------------------

@pytest.mark.asyncio
async def test_set_user_policies_writes_serialized_payload_with_ttl(mocker):
    set_mock = mocker.patch(f"{MODULE}.valkey_client.set", new_callable=AsyncMock)

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
    delete_mock = mocker.patch(f"{MODULE}.valkey_client.delete", new_callable=AsyncMock)

    await authorization_cache_service.invalidate_user_policies("user@example.com")

    delete_mock.assert_awaited_once_with(_user_policies_key("user@example.com"))


# ---------------------------- Invalidate all users ----------------------------

@pytest.mark.asyncio
async def test_invalidate_all_user_policies_deletes_every_matching_key(mocker):
    """Deletes are batched into one DELETE call per SCAN batch (not one
    round trip per key), so this asserts every matched key is covered by
    the delete call(s), not a delete-per-key count."""
    keys = ["authz:user_policies:a@example.com", "authz:user_policies:b@example.com"]

    async def _fake_scan_iter(match):
        for key in keys:
            yield key

    mocker.patch(f"{MODULE}.valkey_client.scan_iter", side_effect=_fake_scan_iter)
    delete_mock = mocker.patch(f"{MODULE}.valkey_client.delete", new_callable=AsyncMock)

    await authorization_cache_service.invalidate_all_user_policies()

    assert delete_mock.await_count == 1
    assert set(delete_mock.await_args.args) == set(keys)


# ---------------------------- Valkey-unavailable fallback ----------------------------

@pytest.mark.asyncio
async def test_get_user_policies_falls_back_to_none_when_valkey_is_unavailable(mocker):
    mocker.patch(f"{MODULE}.valkey_client.get", new_callable=AsyncMock, side_effect=ConnectionError("valkey down"))

    result = await authorization_cache_service.get_user_policies("user@example.com")

    assert result is None  # caller treats this exactly like a cache miss -> queries the DB


@pytest.mark.asyncio
async def test_set_user_policies_swallows_valkey_errors_without_raising(mocker):
    mocker.patch(f"{MODULE}.valkey_client.set", new_callable=AsyncMock, side_effect=ConnectionError("valkey down"))

    await authorization_cache_service.set_user_policies("user@example.com", [_policy()])  # must not raise


@pytest.mark.asyncio
async def test_invalidate_user_policies_swallows_valkey_errors_without_raising(mocker):
    mocker.patch(f"{MODULE}.valkey_client.delete", new_callable=AsyncMock, side_effect=ConnectionError("valkey down"))

    await authorization_cache_service.invalidate_user_policies("user@example.com")  # must not raise


@pytest.mark.asyncio
async def test_get_user_policies_corrupt_payload_returns_none_not_a_crash(mocker):
    mocker.patch(f"{MODULE}.valkey_client.get", new_callable=AsyncMock, return_value="not-valid-json{{{")

    result = await authorization_cache_service.get_user_policies("user@example.com")

    assert result is None


@pytest.mark.asyncio
async def test_user_permissions_cache_round_trip_and_corrupt_payload(mocker):
    payload = json.dumps([{
        "action": "users:read_own",
        "resource_type": "users",
        "conditions": {"owner": True},
        "is_active": True,
    }])
    get_mock = mocker.patch(f"{MODULE}.valkey_client.get", new_callable=AsyncMock, return_value=payload)
    set_mock = mocker.patch(f"{MODULE}.valkey_client.set", new_callable=AsyncMock)

    result = await authorization_cache_service.get_user_permissions("user@example.com")
    await authorization_cache_service.set_user_permissions("user@example.com", [_grant(conditions={"owner": True})])

    assert result is not None
    assert result[0].action == "users:read_own"
    get_mock.assert_awaited_once_with(_user_permissions_key("user@example.com"))
    assert json.loads(set_mock.await_args.args[1])[0]["conditions"] == {"owner": True}

    get_mock.reset_mock()
    get_mock.return_value = "not-json"
    assert await authorization_cache_service.get_user_permissions("user@example.com") is None


@pytest.mark.asyncio
async def test_user_permission_invalidation_supports_single_bulk_empty_and_failure(mocker):
    delete_mock = mocker.patch(f"{MODULE}.valkey_client.delete", new_callable=AsyncMock)

    await authorization_cache_service.invalidate_user_permissions("user@example.com")
    await authorization_cache_service.invalidate_user_permissions_bulk(set())
    await authorization_cache_service.invalidate_user_permissions_bulk({"a@example.com", "b@example.com"})

    assert delete_mock.await_count == 2
    assert set(delete_mock.await_args.args) == {
        _user_permissions_key("a@example.com"),
        _user_permissions_key("b@example.com"),
    }

    delete_mock.side_effect = ConnectionError("valkey down")
    await authorization_cache_service.invalidate_user_permissions("user@example.com")
    await authorization_cache_service.invalidate_user_permissions_bulk({"user@example.com"})


@pytest.mark.asyncio
async def test_policy_bulk_invalidation_handles_empty_and_valkey_failure(mocker):
    delete_mock = mocker.patch(f"{MODULE}.valkey_client.delete", new_callable=AsyncMock)
    error_mock = mocker.patch(f"{MODULE}.logger.warning")

    await authorization_cache_service.invalidate_user_policies_bulk(set())
    delete_mock.assert_not_awaited()

    delete_mock.side_effect = ConnectionError("valkey down")
    await authorization_cache_service.invalidate_user_policies_bulk({"user@example.com"})
    error_mock.assert_called_once()


@pytest.mark.asyncio
async def test_policy_namespace_invalidation_flushes_full_batches_and_tail(mocker):
    keys = [f"authz:user_policies:{index}@example.com" for index in range(501)]

    async def _fake_scan_iter(match):
        for key in keys:
            yield key

    mocker.patch(f"{MODULE}.valkey_client.scan_iter", side_effect=_fake_scan_iter)
    delete_mock = mocker.patch(f"{MODULE}.valkey_client.delete", new_callable=AsyncMock)

    await authorization_cache_service.invalidate_all_user_policies()

    assert delete_mock.await_count == 2
    assert len(delete_mock.await_args_list[0].args) == 500
    assert len(delete_mock.await_args_list[1].args) == 1
