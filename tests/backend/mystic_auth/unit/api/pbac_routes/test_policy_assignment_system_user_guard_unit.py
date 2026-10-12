# assign_policy_to_user, remove_policy_from_user, and
# revoke_policy_action_from_user (policy_assignment_routes.py) all refuse
# to touch a UserRole.system target ("SYSTEM_USER_CANNOT_BE_MODIFIED")
# before any escalation/lockout check runs. This suite sets `.role` to
# UserRole.system on the target user to exercise that guard.
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from backend.mystic_auth.api.pbac_routes.policies.policy_assignment_routes import (
    assign_policy_to_user,
    remove_policy_from_user,
    revoke_policy_action_from_user,
)
from backend.mystic_auth.authorization.schemas.policy_schema import (
    PolicyActionRevocationRequest,
    PolicyAssignmentRequest,
)
from backend.mystic_auth.user.user_model import UserRole

SERVICE_MODULE = "backend.mystic_auth.authorization.services.authorization_service"
ASSIGNMENT_ROUTES_MODULE = "backend.mystic_auth.api.pbac_routes.policies.policy_assignment_routes"

CALLER = {"email": "caller@example.com", "name": "Caller"}


def _make_policy(**overrides):
    policy = MagicMock()
    policy.id = 1
    policy.name = "some_policy"
    policy.actions = ["users:read_own"]
    policy.resource_type = "users"
    for key, value in overrides.items():
        setattr(policy, key, value)
    return policy


def _make_system_user(email="system@example.com"):
    user = MagicMock()
    user.id = 99
    user.email = email
    user.role = UserRole.system
    return user


@pytest.mark.asyncio
async def test_assign_policy_to_system_user_is_rejected(mocker):
    system_user = _make_system_user()
    policy = _make_policy()
    mocker.patch(f"{ASSIGNMENT_ROUTES_MODULE}.user_crud.get_by_email", new_callable=AsyncMock, return_value=system_user)
    mocker.patch(f"{ASSIGNMENT_ROUTES_MODULE}.policy_repository.get_by_name", new_callable=AsyncMock, return_value=policy)
    guard_mock = mocker.patch(f"{SERVICE_MODULE}.AuthorizationService.assert_authorized_to_grant", new_callable=AsyncMock)
    assign_mock = mocker.patch(f"{ASSIGNMENT_ROUTES_MODULE}.policy_repository.assign_policy_to_user", new_callable=AsyncMock)

    with pytest.raises(HTTPException) as exc_info:
        await assign_policy_to_user(
            system_user.email, PolicyAssignmentRequest(policy_name="some_policy"),
            request=MagicMock(), current_user=CALLER, db="fake-db",
        )

    assert exc_info.value.status_code == 403
    assert exc_info.value.code == "SYSTEM_USER_CANNOT_BE_MODIFIED"
    guard_mock.assert_not_awaited()
    assign_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_remove_policy_from_system_user_is_rejected(mocker):
    system_user = _make_system_user()
    policy = _make_policy()
    mocker.patch(f"{ASSIGNMENT_ROUTES_MODULE}.user_crud.get_by_email", new_callable=AsyncMock, return_value=system_user)
    mocker.patch(f"{ASSIGNMENT_ROUTES_MODULE}.policy_repository.get_by_name", new_callable=AsyncMock, return_value=policy)
    guard_mock = mocker.patch(f"{SERVICE_MODULE}.AuthorizationService.assert_authorized_to_grant", new_callable=AsyncMock)
    holds_mock = mocker.patch(f"{ASSIGNMENT_ROUTES_MODULE}.policy_repository.user_holds_policy", new_callable=AsyncMock)
    remove_mock = mocker.patch(f"{ASSIGNMENT_ROUTES_MODULE}.policy_repository.remove_policy_from_user", new_callable=AsyncMock)

    with pytest.raises(HTTPException) as exc_info:
        await remove_policy_from_user(
            system_user.email, "some_policy", request=MagicMock(), current_user=CALLER, db="fake-db",
        )

    assert exc_info.value.status_code == 403
    assert exc_info.value.code == "SYSTEM_USER_CANNOT_BE_MODIFIED"
    # The system-user check must short-circuit before even the holdership
    # check or the escalation guard run.
    guard_mock.assert_not_awaited()
    holds_mock.assert_not_awaited()
    remove_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_revoke_policy_action_from_system_user_is_rejected(mocker):
    system_user = _make_system_user()
    policy = _make_policy()
    mocker.patch(f"{ASSIGNMENT_ROUTES_MODULE}.user_crud.get_by_email", new_callable=AsyncMock, return_value=system_user)
    mocker.patch(f"{ASSIGNMENT_ROUTES_MODULE}.policy_repository.get_by_name", new_callable=AsyncMock, return_value=policy)
    guard_mock = mocker.patch(f"{SERVICE_MODULE}.AuthorizationService.assert_authorized_to_grant", new_callable=AsyncMock)
    revoke_mock = mocker.patch(
        f"{ASSIGNMENT_ROUTES_MODULE}.policy_action_revocation_service.revoke_single_action", new_callable=AsyncMock
    )

    with pytest.raises(HTTPException) as exc_info:
        await revoke_policy_action_from_user(
            system_user.email, "some_policy",
            PolicyActionRevocationRequest(action="users:read_own"),
            request=MagicMock(), current_user=CALLER, _permissions_grant=CALLER, db="fake-db",
        )

    assert exc_info.value.status_code == 403
    assert exc_info.value.code == "SYSTEM_USER_CANNOT_BE_MODIFIED"
    guard_mock.assert_not_awaited()
    revoke_mock.assert_not_awaited()
