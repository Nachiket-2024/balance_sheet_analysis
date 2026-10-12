from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from backend.mystic_auth.api.pbac_routes.permissions.permission_assignment_routes import (
    grant_permission_to_user,
)
from backend.mystic_auth.authorization.schemas.permission_schema import (
    PermissionAssignmentRequest,
    UserPermissionRead,
)

ROUTES_MODULE = "backend.mystic_auth.api.pbac_routes.permissions.permission_assignment_routes"
SERVICE_MODULE = "backend.mystic_auth.authorization.services.authorization_service"

CALLER = {"email": "caller@example.com", "name": "Caller"}


def _make_user(email="target@example.com"):
    user = MagicMock()
    user.id = 1
    user.email = email
    user.role = None
    return user


@pytest.mark.asyncio
async def test_grant_permission_rejects_invalid_conditions_before_touching_repository(mocker):
    target = _make_user()
    mocker.patch(f"{ROUTES_MODULE}.user_crud.get_by_email", new_callable=AsyncMock, return_value=target)
    guard_mock = mocker.patch(f"{SERVICE_MODULE}.AuthorizationService.assert_authorized_to_grant", new_callable=AsyncMock)
    assign_mock = mocker.patch(
        f"{ROUTES_MODULE}.user_permission_repository.assign_permission_to_user", new_callable=AsyncMock
    )

    with pytest.raises(HTTPException) as exc_info:
        await grant_permission_to_user(
            target.email,
            PermissionAssignmentRequest(
                action="users:read_own",
                resource_type="users",
                conditions={"network": {"allowed_ips": ["not-an-ip"]}},
            ),
            request=MagicMock(),
            current_user=CALLER,
            db="fake-db",
        )

    assert exc_info.value.status_code == 422
    assert exc_info.value.code == "INVALID_CONDITIONS"
    guard_mock.assert_not_awaited()
    assign_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_grant_permission_allows_valid_conditions(mocker):
    target = _make_user()
    mocker.patch(f"{ROUTES_MODULE}.user_crud.get_by_email", new_callable=AsyncMock, return_value=target)
    mocker.patch(f"{SERVICE_MODULE}.AuthorizationService.assert_authorized_to_grant", new_callable=AsyncMock)
    assign_mock = mocker.patch(
        f"{ROUTES_MODULE}.user_permission_repository.assign_permission_to_user", new_callable=AsyncMock
    )
    mocker.patch(f"{ROUTES_MODULE}.log_security_event", new_callable=AsyncMock)
    mocker.patch(f"{ROUTES_MODULE}.publish_permissions_changed", new_callable=AsyncMock)

    await grant_permission_to_user(
        target.email,
        PermissionAssignmentRequest(
            action="users:read_own",
            resource_type="users",
            conditions={"self_only": True},
        ),
        request=MagicMock(),
        current_user=CALLER,
        db="fake-db",
    )

    assign_mock.assert_awaited_once()


def test_user_permission_read_sanitizes_oversized_legacy_conditions():
    oversized_conditions = {"context_attributes": {f"k{i}": i for i in range(2001)}}

    result = UserPermissionRead(
        id=1,
        action="users:read_own",
        resource_type="users",
        conditions=oversized_conditions,
        is_active=True,
        assigned_by="admin@example.com",
    )

    assert result.conditions == {
        "_error": "conditions omitted: exceeds size/depth limits, needs repair via direct DB access"
    }
