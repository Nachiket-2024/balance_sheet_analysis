# grant_permission_to_user and revoke_permission_from_user
# (permission_assignment_routes.py) both refuse to touch a UserRole.system
# target ("SYSTEM_USER_CANNOT_BE_MODIFIED"), mirroring the same guard on
# update_user_role/update_user and on policy_assignment_routes.py. This is
# the first suite to actually set `.role` to UserRole.system on the target
# user, exercising that branch.
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from backend.mystic_auth.api.pbac_routes.permissions.permission_assignment_routes import (
    grant_permission_to_user,
    revoke_permission_from_user,
)
from backend.mystic_auth.authorization.schemas.permission_schema import (
    PermissionAssignmentRequest,
)
from backend.mystic_auth.user.user_model import UserRole

SERVICE_MODULE = "backend.mystic_auth.authorization.services.authorization_service"
ROUTES_MODULE = "backend.mystic_auth.api.pbac_routes.permissions.permission_assignment_routes"

CALLER = {"email": "caller@example.com", "name": "Caller"}


def _make_system_user(email="system@example.com"):
    user = MagicMock()
    user.id = 99
    user.email = email
    user.role = UserRole.system
    return user


@pytest.mark.asyncio
async def test_grant_permission_to_system_user_is_rejected(mocker):
    system_user = _make_system_user()
    mocker.patch(f"{ROUTES_MODULE}.user_crud.get_by_email", new_callable=AsyncMock, return_value=system_user)
    guard_mock = mocker.patch(f"{SERVICE_MODULE}.AuthorizationService.assert_authorized_to_grant", new_callable=AsyncMock)
    assign_mock = mocker.patch(
        f"{ROUTES_MODULE}.user_permission_repository.assign_permission_to_user", new_callable=AsyncMock
    )

    with pytest.raises(HTTPException) as exc_info:
        await grant_permission_to_user(
            system_user.email,
            PermissionAssignmentRequest(action="users:read_own", resource_type="users"),
            request=MagicMock(),
            current_user=CALLER, db="fake-db",
        )

    assert exc_info.value.status_code == 403
    assert exc_info.value.code == "SYSTEM_USER_CANNOT_BE_MODIFIED"
    # The escalation guard and the actual write must never even run once the
    # system-user check has already rejected the request.
    guard_mock.assert_not_awaited()
    assign_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_revoke_permission_from_system_user_is_rejected(mocker):
    system_user = _make_system_user()
    mocker.patch(f"{ROUTES_MODULE}.user_crud.get_by_email", new_callable=AsyncMock, return_value=system_user)
    guard_mock = mocker.patch(f"{SERVICE_MODULE}.AuthorizationService.assert_authorized_to_grant", new_callable=AsyncMock)
    remove_mock = mocker.patch(
        f"{ROUTES_MODULE}.user_permission_repository.remove_permission_from_user", new_callable=AsyncMock
    )

    with pytest.raises(HTTPException) as exc_info:
        await revoke_permission_from_user(
            system_user.email, "users:read_own", "users",
            request=MagicMock(),
            current_user=CALLER, db="fake-db",
        )

    assert exc_info.value.status_code == 403
    assert exc_info.value.code == "SYSTEM_USER_CANNOT_BE_MODIFIED"
    guard_mock.assert_not_awaited()
    remove_mock.assert_not_awaited()
