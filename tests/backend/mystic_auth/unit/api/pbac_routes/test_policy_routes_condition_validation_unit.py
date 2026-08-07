# tests/backend/mystic_auth/unit/api/pbac_routes/test_policy_routes_condition_validation_unit.py
#
# Proves create_policy/update_policy reject a malformed `conditions` block
# with 422 *before* touching the repository ("Must happen
# before database writes") : and that a valid conditions block passes
# through untouched.
from unittest.mock import AsyncMock, MagicMock

import pytest
from backend.mystic_auth.api.pbac_routes.policy_crud_routes import (
    create_policy,
    update_policy,
)
from backend.mystic_auth.authorization.policies.default_policies import (
    SYSTEM_SUPERUSER_POLICY_NAME,
)
from backend.mystic_auth.authorization.schemas.policy_schema import (
    PolicyCreate,
    PolicyUpdate,
)
from fastapi import HTTPException

ROUTES_MODULE = "backend.mystic_auth.api.pbac_routes.policy_crud_routes"
SERVICE_MODULE = "backend.mystic_auth.authorization.services.authorization_service"

CALLER = {"email": "caller@example.com", "name": "Caller"}


def _make_policy(**overrides):
    policy = MagicMock()
    policy.id = 1
    policy.name = "some_policy"
    policy.actions = ["users:read_own"]
    policy.resource_type = "users"
    policy.conditions = None
    policy.is_active = True
    for key, value in overrides.items():
        setattr(policy, key, value)
    return policy


@pytest.mark.asyncio
async def test_create_policy_rejects_invalid_conditions_before_touching_repository(mocker):
    policy_data = PolicyCreate(
        name="bad_policy", actions=["users:read_own"], resource_type="users",
        conditions={"time": {"start": "not-a-time", "end": "17:00"}},
    )
    get_by_name_mock = mocker.patch(f"{ROUTES_MODULE}.policy_repository.get_by_name", new_callable=AsyncMock)
    create_mock = mocker.patch(f"{ROUTES_MODULE}.policy_repository.create", new_callable=AsyncMock)

    with pytest.raises(HTTPException) as exc_info:
        await create_policy(policy_data, current_user=CALLER, db="fake-db")

    assert exc_info.value.status_code == 422
    get_by_name_mock.assert_not_called()
    create_mock.assert_not_called()


@pytest.mark.asyncio
async def test_create_policy_rejects_unknown_condition_key(mocker):
    policy_data = PolicyCreate(
        name="bad_policy", actions=["users:read_own"], resource_type="users",
        conditions={"made_up_condition": True},
    )
    mocker.patch(f"{ROUTES_MODULE}.policy_repository.get_by_name", new_callable=AsyncMock)
    create_mock = mocker.patch(f"{ROUTES_MODULE}.policy_repository.create", new_callable=AsyncMock)

    with pytest.raises(HTTPException) as exc_info:
        await create_policy(policy_data, current_user=CALLER, db="fake-db")

    assert exc_info.value.status_code == 422
    create_mock.assert_not_called()


@pytest.mark.asyncio
async def test_create_policy_allows_valid_conditions(mocker):
    policy_data = PolicyCreate(
        name="good_policy", actions=["users:read_own"], resource_type="users",
        conditions={"time": {"start": "09:00", "end": "17:00", "timezone": "UTC"}},
    )
    created = _make_policy(name="good_policy")
    mocker.patch(f"{ROUTES_MODULE}.policy_repository.get_by_name", new_callable=AsyncMock, return_value=None)
    mocker.patch(f"{ROUTES_MODULE}.policy_repository.create", new_callable=AsyncMock, return_value=created)
    mocker.patch(f"{SERVICE_MODULE}.AuthorizationService.authorize", new_callable=AsyncMock, return_value=True)

    result = await create_policy(policy_data, current_user=CALLER, db="fake-db")

    assert result is created


@pytest.mark.asyncio
async def test_update_policy_rejects_invalid_conditions_before_touching_repository(mocker):
    policy = _make_policy()
    update_data = PolicyUpdate(conditions={"network": {"allowed_ips": ["not-an-ip"]}})
    mocker.patch(f"{ROUTES_MODULE}.policy_repository.get_by_name", new_callable=AsyncMock, return_value=policy)
    update_mock = mocker.patch(f"{ROUTES_MODULE}.policy_repository.update", new_callable=AsyncMock)

    with pytest.raises(HTTPException) as exc_info:
        await update_policy("some_policy", update_data, current_user=CALLER, db="fake-db")

    assert exc_info.value.status_code == 422
    update_mock.assert_not_called()


@pytest.mark.asyncio
async def test_update_policy_does_not_validate_when_conditions_untouched(mocker):
    """A caller who isn't changing conditions at all (e.g. only flipping
    is_active) must not be blocked by conditions validation."""
    policy = _make_policy(conditions={"self_only": True})
    update_data = PolicyUpdate(is_active=False)
    mocker.patch(f"{ROUTES_MODULE}.policy_repository.get_by_name", new_callable=AsyncMock, return_value=policy)
    update_mock = mocker.patch(f"{ROUTES_MODULE}.policy_repository.update", new_callable=AsyncMock, return_value=policy)

    await update_policy("some_policy", update_data, current_user=CALLER, db="fake-db")

    update_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_policy_rejects_deactivating_a_baseline_policy(mocker):
    # is_active=False excludes a policy from evaluation for every holder at
    # once (see policy_repository.py) : for system_superuser, that would
    # silently strip every superuser (including the true system account) of
    # all access, bypassing both the rename/delete guards and the separate
    # "last remaining assignment" lockout guard on remove_policy_from_user
    # (a different endpoint this update doesn't go through). This must be
    # rejected even though "actions" isn't being touched at all, so
    # assert_authorized_to_grant is never reached/relevant here.
    policy = _make_policy(name=SYSTEM_SUPERUSER_POLICY_NAME)
    update_data = PolicyUpdate(is_active=False)
    mocker.patch(f"{ROUTES_MODULE}.policy_repository.get_by_name", new_callable=AsyncMock, return_value=policy)
    update_mock = mocker.patch(f"{ROUTES_MODULE}.policy_repository.update", new_callable=AsyncMock)

    with pytest.raises(HTTPException) as exc_info:
        await update_policy(SYSTEM_SUPERUSER_POLICY_NAME, update_data, current_user=CALLER, db="fake-db")

    assert exc_info.value.status_code == 403
    update_mock.assert_not_called()


@pytest.mark.asyncio
async def test_update_policy_allows_reactivating_a_baseline_policy(mocker):
    # Only is_active=False (deactivation) is blocked : re-activating a
    # baseline policy that was somehow already inactive must still work.
    policy = _make_policy(name=SYSTEM_SUPERUSER_POLICY_NAME, is_active=False)
    update_data = PolicyUpdate(is_active=True)
    mocker.patch(f"{ROUTES_MODULE}.policy_repository.get_by_name", new_callable=AsyncMock, return_value=policy)
    update_mock = mocker.patch(f"{ROUTES_MODULE}.policy_repository.update", new_callable=AsyncMock, return_value=policy)

    await update_policy(SYSTEM_SUPERUSER_POLICY_NAME, update_data, current_user=CALLER, db="fake-db")

    update_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_policy_allows_explicitly_clearing_conditions_to_null(mocker):
    policy = _make_policy(conditions={"self_only": True})
    update_data = PolicyUpdate(conditions=None)
    mocker.patch(f"{ROUTES_MODULE}.policy_repository.get_by_name", new_callable=AsyncMock, return_value=policy)
    update_mock = mocker.patch(f"{ROUTES_MODULE}.policy_repository.update", new_callable=AsyncMock, return_value=policy)

    await update_policy("some_policy", update_data, current_user=CALLER, db="fake-db")

    update_mock.assert_awaited_once()
