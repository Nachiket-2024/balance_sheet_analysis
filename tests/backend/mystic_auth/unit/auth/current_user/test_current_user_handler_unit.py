# current_user_handler.py backs GET /auth/me. These tests pin down its PBAC
# behavior: the 'permissions' it returns must come from the caller's
# assigned policies (via policy_repository) and their direct
# UserPermission grants (via user_permission_repository), never from
# their role. Two users with the same role can hold different
# policies/grants and see different permissions here. The direct-grant
# half mirrors AuthorizationService._get_effective_policies, which real
# backend enforcement merges the same way, so a directly-granted action
# doesn't pass every real check yet stay invisible in the frontend (which
# reads only this list).
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException, status
from sqlalchemy.exc import SQLAlchemyError

from backend.mystic_auth.auth.current_user.current_user_handler import (
    current_user_handler,
)
from backend.mystic_auth.core.errors import AppError
from backend.mystic_auth.user.user_model import UserRole

MODULE = "backend.mystic_auth.auth.current_user.current_user_handler"


class _FakeUser:
    def __init__(
        self, name="Test User", email="user@example.com", role="user", is_active=True, hashed_password="hash",
        created_at=None, brand_color=None,
    ):
        self.name = name
        self.email = email
        self.role = UserRole(role) if role is not None else None
        self.is_active = is_active
        self.hashed_password = hashed_password
        self.created_at = created_at or datetime(2026, 1, 1, tzinfo=UTC)
        self.brand_color = brand_color


class _FakePolicy:
    def __init__(self, actions, resource_type="users"):
        self.actions = actions
        # Every action below is "users:...", so "users" is a correct
        # default here; a test that wants cross-resource-type filtering
        # passes resource_type explicitly.
        self.resource_type = resource_type


class _FakeGrant:
    """Stands in for a UserPermission row: a direct (bypasses-Policy) grant
    of exactly one action. Same resource_type default/override convention
    as _FakePolicy above."""

    def __init__(self, action, resource_type="users"):
        self.action = action
        self.resource_type = resource_type


def _mock_no_direct_grants(mocker):
    """Most tests here aren't exercising direct grants; this keeps them
    from needing to know that call exists."""
    mocker.patch(
        f"{MODULE}.user_permission_repository.get_active_permissions_for_user",
        new_callable=AsyncMock,
        return_value=[],
    )


def _patch_identity(mocker, *, payload=None, user=None, token_error=None, lookup_error=None):
    mocker.patch(
        f"{MODULE}.jwt_service.verify_token",
        new_callable=AsyncMock,
        side_effect=token_error,
        return_value=payload,
    )
    mocker.patch(
        f"{MODULE}.user_crud.get_by_email",
        new_callable=AsyncMock,
        side_effect=lookup_error,
        return_value=user,
    )


@pytest.mark.asyncio
async def test_missing_access_token_returns_stable_unauthorized_error(mocker):
    verify = mocker.patch(f"{MODULE}.jwt_service.verify_token", new_callable=AsyncMock)

    with pytest.raises(AppError) as exc_info:
        await current_user_handler.get_current_user("", db=None)

    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert exc_info.value.code == "NO_ACCESS_TOKEN"
    verify.assert_not_awaited()


@pytest.mark.parametrize(
    ("payload", "expected_code"),
    [(None, "INVALID_OR_EXPIRED_TOKEN"), ({"sub": "missing-email"}, "INVALID_TOKEN_PAYLOAD")],
)
@pytest.mark.asyncio
async def test_invalid_or_incomplete_access_token_returns_unauthorized(mocker, payload, expected_code):
    _patch_identity(mocker, payload=payload)
    lookup = mocker.patch(f"{MODULE}.user_crud.get_by_email", new_callable=AsyncMock)

    with pytest.raises(AppError) as exc_info:
        await current_user_handler.get_current_user("token", db=None)

    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert exc_info.value.code == expected_code
    lookup.assert_not_awaited()


@pytest.mark.parametrize(
    ("user", "expected_status", "expected_code"),
    [
        (None, status.HTTP_401_UNAUTHORIZED, "USER_NOT_FOUND"),
        (_FakeUser(is_active=False), status.HTTP_403_FORBIDDEN, "ACCOUNT_DEACTIVATED"),
    ],
)
@pytest.mark.asyncio
async def test_missing_or_deactivated_account_is_rejected(mocker, user, expected_status, expected_code):
    _patch_identity(mocker, payload={"email": "user@example.com"}, user=user)

    with pytest.raises(AppError) as exc_info:
        await current_user_handler.get_current_user("token", db=None)

    assert exc_info.value.status_code == expected_status
    assert exc_info.value.code == expected_code


@pytest.mark.asyncio
async def test_database_failure_maps_to_safe_database_error(mocker):
    _patch_identity(
        mocker,
        payload={"email": "user@example.com"},
        lookup_error=SQLAlchemyError("private database detail"),
    )

    with pytest.raises(AppError) as exc_info:
        await current_user_handler.get_current_user("token", db=None)

    assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert exc_info.value.code == "DATABASE_ERROR"
    assert exc_info.value.detail == "Database error"


@pytest.mark.asyncio
async def test_unexpected_failure_maps_to_safe_internal_error(mocker):
    _patch_identity(mocker, payload={"email": "user@example.com"}, user=_FakeUser())
    mocker.patch(
        f"{MODULE}.policy_repository.get_active_policies_for_user",
        new_callable=AsyncMock,
        side_effect=RuntimeError("private service detail"),
    )

    with pytest.raises(AppError) as exc_info:
        await current_user_handler.get_current_user("token", db=None)

    assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert exc_info.value.code == "INTERNAL_SERVER_ERROR"
    assert exc_info.value.detail == "Internal server error"


@pytest.mark.asyncio
async def test_existing_http_exception_passes_through_unchanged(mocker):
    expected = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Rejected")
    _patch_identity(mocker, token_error=expected)

    with pytest.raises(HTTPException) as exc_info:
        await current_user_handler.get_current_user("token", db=None)

    assert exc_info.value is expected


@pytest.mark.asyncio
async def test_permissions_are_the_union_of_the_users_assigned_policies(mocker):
    mocker.patch(
        f"{MODULE}.jwt_service.verify_token",
        new_callable=AsyncMock,
        return_value={"email": "user@example.com", "role": "user"},
    )
    mocker.patch(f"{MODULE}.user_crud.get_by_email", return_value=_FakeUser())
    mocker.patch(
        f"{MODULE}.policy_repository.get_active_policies_for_user",
        new_callable=AsyncMock,
        return_value=[
            _FakePolicy(["users:read_own", "users:update_own"]),
            _FakePolicy(["users:list_all"]),
        ],
    )

    _mock_no_direct_grants(mocker)

    result = await current_user_handler.get_current_user("some-token", db=None)

    assert result["permissions"] == ["users:list_all", "users:read_own", "users:update_own"]


@pytest.mark.asyncio
async def test_no_assigned_policies_means_no_permissions(mocker):
    mocker.patch(
        f"{MODULE}.jwt_service.verify_token",
        new_callable=AsyncMock,
        return_value={"email": "user@example.com", "role": "user"},
    )
    mocker.patch(f"{MODULE}.user_crud.get_by_email", return_value=_FakeUser())
    mocker.patch(
        f"{MODULE}.policy_repository.get_active_policies_for_user",
        new_callable=AsyncMock,
        return_value=[],
    )

    _mock_no_direct_grants(mocker)

    result = await current_user_handler.get_current_user("some-token", db=None)

    assert result["permissions"] == []


@pytest.mark.asyncio
async def test_two_users_with_the_same_role_can_have_different_permissions(mocker):
    # The core PBAC claim: identical roles can have different permissions.
    mocker.patch(
        f"{MODULE}.jwt_service.verify_token",
        new_callable=AsyncMock,
        side_effect=[
            {"email": "admin-a@example.com", "role": "admin"},
            {"email": "admin-b@example.com", "role": "admin"},
        ],
    )
    mocker.patch(
        f"{MODULE}.user_crud.get_by_email",
        side_effect=[
            _FakeUser(email="admin-a@example.com", role="admin"),
            _FakeUser(email="admin-b@example.com", role="admin"),
        ],
    )
    mocker.patch(
        f"{MODULE}.policy_repository.get_active_policies_for_user",
        new_callable=AsyncMock,
        side_effect=[
            [_FakePolicy(["users:read_own", "users:update_own", "users:list_all"])],
            [_FakePolicy(["users:read_own", "users:update_own"])],
        ],
    )

    _mock_no_direct_grants(mocker)

    result_a = await current_user_handler.get_current_user("token-a", db=None)
    result_b = await current_user_handler.get_current_user("token-b", db=None)

    assert result_a["role"] == result_b["role"] == "admin"
    assert result_a["permissions"] != result_b["permissions"]
    assert "users:list_all" in result_a["permissions"]
    assert "users:list_all" not in result_b["permissions"]


# ---------------------------- Users without roles ----------------------------
# role is metadata only: a roleless account must still authenticate and
# be authorized purely via its assigned policies.

@pytest.mark.asyncio
async def test_a_user_with_no_role_at_all_is_still_authenticated(mocker):
    mocker.patch(
        f"{MODULE}.jwt_service.verify_token",
        new_callable=AsyncMock,
        return_value={"email": "roleless@example.com", "role": None},
    )
    mocker.patch(
        f"{MODULE}.user_crud.get_by_email",
        return_value=_FakeUser(email="roleless@example.com", role=None),
    )
    mocker.patch(
        f"{MODULE}.policy_repository.get_active_policies_for_user",
        new_callable=AsyncMock,
        return_value=[_FakePolicy(["users:read_own", "users:update_own"])],
    )

    _mock_no_direct_grants(mocker)

    result = await current_user_handler.get_current_user("some-token", db=None)

    assert result["email"] == "roleless@example.com"
    assert result["role"] is None
    assert result["permissions"] == ["users:read_own", "users:update_own"]


@pytest.mark.asyncio
async def test_a_user_with_no_role_gets_admin_level_permissions_if_assigned_admin_policies(mocker):
    # A roleless account isn't limited to "basic" access: it gets exactly
    # whatever its assigned policies grant, same as any other account.
    mocker.patch(
        f"{MODULE}.jwt_service.verify_token",
        new_callable=AsyncMock,
        return_value={"email": "roleless-admin@example.com", "role": None},
    )
    mocker.patch(
        f"{MODULE}.user_crud.get_by_email",
        return_value=_FakeUser(email="roleless-admin@example.com", role=None),
    )
    mocker.patch(
        f"{MODULE}.policy_repository.get_active_policies_for_user",
        new_callable=AsyncMock,
        return_value=[_FakePolicy(["users:list_all", "users:update_any", "users:deactivate_any"])],
    )

    _mock_no_direct_grants(mocker)

    result = await current_user_handler.get_current_user("some-token", db=None)

    assert result["role"] is None
    assert result["permissions"] == ["users:deactivate_any", "users:list_all", "users:update_any"]


# -------------------- Direct (bypasses-Policy) UserPermission grants --------------------
# A UserPermission grant (never through a Policy) must show up here
# exactly like a policy-derived action does: AuthorizationService
# already merges both for real enforcement, so a caller granted only a
# direct permission passes every real check but would see none of the
# corresponding UI if this response omitted it, since every
# IfCan/ProtectedRoute check reads only this permissions list.

@pytest.mark.asyncio
async def test_a_direct_grant_with_no_assigned_policies_at_all_still_appears(mocker):
    mocker.patch(
        f"{MODULE}.jwt_service.verify_token",
        new_callable=AsyncMock,
        return_value={"email": "creator@example.com", "role": "user"},
    )
    mocker.patch(f"{MODULE}.user_crud.get_by_email", return_value=_FakeUser(email="creator@example.com"))
    mocker.patch(f"{MODULE}.policy_repository.get_active_policies_for_user", new_callable=AsyncMock, return_value=[])
    mocker.patch(
        f"{MODULE}.user_permission_repository.get_active_permissions_for_user",
        new_callable=AsyncMock,
        return_value=[_FakeGrant("policies:create", resource_type="policies")],
    )

    result = await current_user_handler.get_current_user("some-token", db=None)

    assert result["permissions"] == ["policies:create"]


@pytest.mark.asyncio
async def test_direct_grants_and_policy_derived_actions_are_unioned(mocker):
    mocker.patch(
        f"{MODULE}.jwt_service.verify_token",
        new_callable=AsyncMock,
        return_value={"email": "user@example.com", "role": "user"},
    )
    mocker.patch(f"{MODULE}.user_crud.get_by_email", return_value=_FakeUser())
    mocker.patch(
        f"{MODULE}.policy_repository.get_active_policies_for_user",
        new_callable=AsyncMock,
        return_value=[_FakePolicy(["users:read_own", "users:update_own"])],
    )
    mocker.patch(
        f"{MODULE}.user_permission_repository.get_active_permissions_for_user",
        new_callable=AsyncMock,
        return_value=[_FakeGrant("policies:create", resource_type="policies")],
    )

    result = await current_user_handler.get_current_user("some-token", db=None)

    assert result["permissions"] == ["policies:create", "users:read_own", "users:update_own"]


@pytest.mark.asyncio
async def test_a_direct_grant_already_covered_by_a_policy_is_not_duplicated(mocker):
    mocker.patch(
        f"{MODULE}.jwt_service.verify_token",
        new_callable=AsyncMock,
        return_value={"email": "user@example.com", "role": "user"},
    )
    mocker.patch(f"{MODULE}.user_crud.get_by_email", return_value=_FakeUser())
    mocker.patch(
        f"{MODULE}.policy_repository.get_active_policies_for_user",
        new_callable=AsyncMock,
        return_value=[_FakePolicy(["users:read_own"])],
    )
    mocker.patch(
        f"{MODULE}.user_permission_repository.get_active_permissions_for_user",
        new_callable=AsyncMock,
        return_value=[_FakeGrant("users:read_own")],
    )

    result = await current_user_handler.get_current_user("some-token", db=None)

    assert result["permissions"] == ["users:read_own"]


@pytest.mark.asyncio
async def test_a_direct_grant_scoped_to_the_wrong_resource_type_is_excluded(mocker):
    # Same reasoning as the identical filter on policy actions above: a
    # UserPermission's resource_type is independently editable from its
    # action, so a mis-scoped grant must not light up UI the backend
    # would 403 on for real.
    mocker.patch(
        f"{MODULE}.jwt_service.verify_token",
        new_callable=AsyncMock,
        return_value={"email": "user@example.com", "role": "user"},
    )
    mocker.patch(f"{MODULE}.user_crud.get_by_email", return_value=_FakeUser())
    mocker.patch(f"{MODULE}.policy_repository.get_active_policies_for_user", new_callable=AsyncMock, return_value=[])
    mocker.patch(
        f"{MODULE}.user_permission_repository.get_active_permissions_for_user",
        new_callable=AsyncMock,
        return_value=[_FakeGrant("policies:read", resource_type="users")],
    )

    result = await current_user_handler.get_current_user("some-token", db=None)

    assert result["permissions"] == []


@pytest.mark.asyncio
async def test_a_wildcard_scoped_direct_grant_is_included(mocker):
    mocker.patch(
        f"{MODULE}.jwt_service.verify_token",
        new_callable=AsyncMock,
        return_value={"email": "user@example.com", "role": "user"},
    )
    mocker.patch(f"{MODULE}.user_crud.get_by_email", return_value=_FakeUser())
    mocker.patch(f"{MODULE}.policy_repository.get_active_policies_for_user", new_callable=AsyncMock, return_value=[])
    mocker.patch(
        f"{MODULE}.user_permission_repository.get_active_permissions_for_user",
        new_callable=AsyncMock,
        return_value=[_FakeGrant("policies:read", resource_type="*")],
    )

    result = await current_user_handler.get_current_user("some-token", db=None)

    assert result["permissions"] == ["policies:read"]
