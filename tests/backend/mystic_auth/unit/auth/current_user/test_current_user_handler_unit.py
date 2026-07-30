# tests/backend/mystic_auth/unit/test_current_user_handler_unit.py
#
# current_user_handler.py backs GET /auth/me. These tests pin down its PBAC
# behavior: the 'permissions' it returns must come from the caller's actual
# *assigned policies* (via policy_repository), never from their role. Two
# users with the identical role can hold different policies and therefore
# see different permissions here.
from unittest.mock import AsyncMock

import pytest
from backend.mystic_auth.auth.current_user.current_user_handler import current_user_handler
from backend.mystic_auth.user_table.user_model import UserRole

MODULE = "backend.mystic_auth.auth.current_user.current_user_handler"


class _FakeUser:
    def __init__(
        self, name="Test User", email="user@example.com", role="user", is_active=True, hashed_password="hash"
    ):
        self.name = name
        self.email = email
        self.role = UserRole(role) if role is not None else None
        self.is_active = is_active
        self.hashed_password = hashed_password


class _FakePolicy:
    def __init__(self, actions):
        self.actions = actions


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

    result = await current_user_handler.get_current_user("some-token", db=None)

    assert result["permissions"] == []


@pytest.mark.asyncio
async def test_two_users_with_the_same_role_can_have_different_permissions(mocker):
    # The core PBAC claim claude.md's Testing Requirements calls out
    # explicitly: "identical roles can have different permissions."
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

    result_a = await current_user_handler.get_current_user("token-a", db=None)
    result_b = await current_user_handler.get_current_user("token-b", db=None)

    assert result_a["role"] == result_b["role"] == "admin"
    assert result_a["permissions"] != result_b["permissions"]
    assert "users:list_all" in result_a["permissions"]
    assert "users:list_all" not in result_b["permissions"]


# ---------------------------- Users without roles ----------------------------
# Per claude.md: role is metadata only, and "the system must support ...
# users without roles" / "users without roles still work": a roleless
# account must still authenticate and be authorized purely via its
# assigned policies.

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

    result = await current_user_handler.get_current_user("some-token", db=None)

    assert result["email"] == "roleless@example.com"
    assert result["role"] is None
    assert result["permissions"] == ["users:read_own", "users:update_own"]


@pytest.mark.asyncio
async def test_a_user_with_no_role_gets_admin_level_permissions_if_assigned_admin_policies(mocker):
    # The strongest form of the claim: a roleless account is not limited to
    # "basic" access: it gets exactly whatever its assigned policies grant,
    # same as any other account.
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
        return_value=[_FakePolicy(["users:list_all", "users:update_any", "users:delete_any"])],
    )

    result = await current_user_handler.get_current_user("some-token", db=None)

    assert result["role"] is None
    assert result["permissions"] == ["users:delete_any", "users:list_all", "users:update_any"]
