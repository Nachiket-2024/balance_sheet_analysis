# Every bulk PBAC route (bulk_permission_routes.py, bulk_policy_routes.py)
# checks `user.role == UserRole.system` per item and reports
# "SYSTEM_USER_CANNOT_BE_MODIFIED" for that item without blocking the
# rest of the batch. This suite is the first to actually give a route a
# target with `.role` set to UserRole.system.
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.mystic_auth.api.pbac_routes.bulk.bulk_permission_routes import (
    bulk_assign_permissions,
    bulk_remove_permissions,
)
from backend.mystic_auth.api.pbac_routes.bulk.bulk_policy_routes import (
    bulk_assign_policies,
    bulk_remove_policies,
)
from backend.mystic_auth.authorization.schemas.bulk_schema import (
    BulkItemResult,
    BulkPermissionItem,
    BulkPermissionRemoveItem,
    BulkPermissionRemoveRequest,
    BulkPermissionRequest,
    BulkPolicyItem,
    BulkPolicyRequest,
)
from backend.mystic_auth.user.user_model import UserRole

from .authorization_test_helpers import authorization_decision

PERMISSION_ROUTES_MODULE = "backend.mystic_auth.api.pbac_routes.bulk.bulk_permission_routes"
POLICY_ROUTES_MODULE = "backend.mystic_auth.api.pbac_routes.bulk.bulk_policy_routes"
SERVICE_MODULE = "backend.mystic_auth.authorization.services.authorization_service"

CALLER = {"email": "caller@example.com", "name": "Caller"}


def _make_user(email, role=None):
    user = MagicMock()
    user.id = hash(email) % 10_000
    user.email = email
    user.role = role
    return user


def _make_policy(name="some_policy", **overrides):
    policy = MagicMock()
    policy.id = 1
    policy.name = name
    policy.actions = ["users:read_own"]
    policy.resource_type = "users"
    for key, value in overrides.items():
        setattr(policy, key, value)
    return policy


async def _fake_bulk_permission_result(valid_items, *args, **kwargs):
    return [
        BulkItemResult(user_email=user.email, identifier=item.action, status="success")
        for user, item in valid_items
    ]


async def _fake_bulk_policy_result(valid_items, *args, **kwargs):
    return [
        BulkItemResult(user_email=user.email, identifier=policy.name, status="success")
        for user, policy in valid_items
    ]


@pytest.mark.asyncio
async def test_bulk_assign_permissions_rejects_system_user_but_applies_other_items(mocker):
    system_user = _make_user("system@example.com", role=UserRole.system)
    normal_user = _make_user("normal@example.com")

    mocker.patch(
        f"{PERMISSION_ROUTES_MODULE}.user_crud.get_by_emails", new_callable=AsyncMock,
        return_value={system_user.email: system_user, normal_user.email: normal_user},
    )
    mocker.patch(f"{SERVICE_MODULE}.AuthorizationService.authorize_with_decision", new_callable=AsyncMock, return_value=authorization_decision(True))
    bulk_assign_mock = mocker.patch(
        f"{PERMISSION_ROUTES_MODULE}.user_permission_repository.bulk_assign_permissions",
        new_callable=AsyncMock, side_effect=_fake_bulk_permission_result,
    )

    body = BulkPermissionRequest(items=[
        BulkPermissionItem(user_email=system_user.email, action="users:read_own", resource_type="users"),
        BulkPermissionItem(user_email=normal_user.email, action="users:read_own", resource_type="users"),
    ])

    result = await bulk_assign_permissions(body, MagicMock(), current_user=CALLER, db=MagicMock())

    statuses = {r.user_email: (r.status, r.error) for r in result.results}
    assert statuses[system_user.email] == ("error", "SYSTEM_USER_CANNOT_BE_MODIFIED")
    assert statuses[normal_user.email] == ("success", None)
    (valid_items_arg, *_rest), _kwargs = bulk_assign_mock.call_args
    assert [user.email for user, _item in valid_items_arg] == [normal_user.email]


@pytest.mark.asyncio
async def test_bulk_assign_permissions_rejects_invalid_conditions_before_repository_write(mocker):
    normal_user = _make_user("normal@example.com")

    mocker.patch(
        f"{PERMISSION_ROUTES_MODULE}.user_crud.get_by_emails", new_callable=AsyncMock,
        return_value={normal_user.email: normal_user},
    )
    guard_mock = mocker.patch(f"{SERVICE_MODULE}.AuthorizationService.authorize_with_decision", new_callable=AsyncMock, return_value=authorization_decision(True))
    bulk_assign_mock = mocker.patch(
        f"{PERMISSION_ROUTES_MODULE}.user_permission_repository.bulk_assign_permissions",
        new_callable=AsyncMock, side_effect=_fake_bulk_permission_result,
    )

    body = BulkPermissionRequest(items=[
        BulkPermissionItem(
            user_email=normal_user.email,
            action="users:read_own",
            resource_type="users",
            conditions={"made_up_condition": True},
        ),
    ])

    result = await bulk_assign_permissions(body, MagicMock(), current_user=CALLER, db=MagicMock())

    assert [(r.status, r.error) for r in result.results] == [("error", "INVALID_CONDITIONS")]
    guard_mock.assert_not_awaited()
    bulk_assign_mock.assert_awaited_once()
    (valid_items_arg, *_rest), _kwargs = bulk_assign_mock.call_args
    assert valid_items_arg == []


@pytest.mark.asyncio
async def test_bulk_remove_permissions_rejects_system_user_but_applies_other_items(mocker):
    system_user = _make_user("system@example.com", role=UserRole.system)
    normal_user = _make_user("normal@example.com")

    mocker.patch(
        f"{PERMISSION_ROUTES_MODULE}.user_crud.get_by_emails", new_callable=AsyncMock,
        return_value={system_user.email: system_user, normal_user.email: normal_user},
    )
    mocker.patch(f"{SERVICE_MODULE}.AuthorizationService.authorize_with_decision", new_callable=AsyncMock, return_value=authorization_decision(True))
    bulk_remove_mock = mocker.patch(
        f"{PERMISSION_ROUTES_MODULE}.user_permission_repository.bulk_remove_permissions",
        new_callable=AsyncMock, side_effect=_fake_bulk_permission_result,
    )

    body = BulkPermissionRemoveRequest(items=[
        BulkPermissionRemoveItem(user_email=system_user.email, action="users:read_own", resource_type="users"),
        BulkPermissionRemoveItem(user_email=normal_user.email, action="users:read_own", resource_type="users"),
    ])

    result = await bulk_remove_permissions(body, MagicMock(), current_user=CALLER, db=MagicMock())

    statuses = {r.user_email: (r.status, r.error) for r in result.results}
    assert statuses[system_user.email] == ("error", "SYSTEM_USER_CANNOT_BE_MODIFIED")
    assert statuses[normal_user.email] == ("success", None)
    (valid_items_arg, *_rest), _kwargs = bulk_remove_mock.call_args
    assert [user.email for user, _item in valid_items_arg] == [normal_user.email]


@pytest.mark.asyncio
async def test_bulk_assign_policies_rejects_system_user_but_applies_other_items(mocker):
    system_user = _make_user("system@example.com", role=UserRole.system)
    normal_user = _make_user("normal@example.com")
    policy = _make_policy()

    mocker.patch(
        f"{POLICY_ROUTES_MODULE}.user_crud.get_by_emails", new_callable=AsyncMock,
        return_value={system_user.email: system_user, normal_user.email: normal_user},
    )
    mocker.patch(
        f"{POLICY_ROUTES_MODULE}.policy_repository.get_policies_by_names", new_callable=AsyncMock,
        return_value={policy.name: policy},
    )
    mocker.patch(f"{SERVICE_MODULE}.AuthorizationService.authorize_with_decision", new_callable=AsyncMock, return_value=authorization_decision(True))
    bulk_assign_mock = mocker.patch(
        f"{POLICY_ROUTES_MODULE}.policy_repository.bulk_assign_policies",
        new_callable=AsyncMock, side_effect=_fake_bulk_policy_result,
    )

    body = BulkPolicyRequest(items=[
        BulkPolicyItem(user_email=system_user.email, policy_name=policy.name),
        BulkPolicyItem(user_email=normal_user.email, policy_name=policy.name),
    ])

    result = await bulk_assign_policies(body, MagicMock(), current_user=CALLER, db=MagicMock())

    statuses = {r.user_email: (r.status, r.error) for r in result.results}
    assert statuses[system_user.email] == ("error", "SYSTEM_USER_CANNOT_BE_MODIFIED")
    assert statuses[normal_user.email] == ("success", None)
    (valid_items_arg, *_rest), _kwargs = bulk_assign_mock.call_args
    assert [user.email for user, _p in valid_items_arg] == [normal_user.email]


@pytest.mark.asyncio
async def test_bulk_remove_policies_rejects_system_user_but_applies_other_items(mocker):
    """Also confirms the system-user check runs before the system_superuser
    last-holder lockout accounting: get_holder_emails must never be
    consulted for a rejected item."""
    system_user = _make_user("system@example.com", role=UserRole.system)
    normal_user = _make_user("normal@example.com")
    policy = _make_policy(name="user_management")

    mocker.patch(
        f"{POLICY_ROUTES_MODULE}.user_crud.get_by_emails", new_callable=AsyncMock,
        return_value={system_user.email: system_user, normal_user.email: normal_user},
    )
    mocker.patch(
        f"{POLICY_ROUTES_MODULE}.policy_repository.get_policies_by_names", new_callable=AsyncMock,
        return_value={policy.name: policy},
    )
    mocker.patch(f"{SERVICE_MODULE}.AuthorizationService.authorize_with_decision", new_callable=AsyncMock, return_value=authorization_decision(True))
    bulk_remove_mock = mocker.patch(
        f"{POLICY_ROUTES_MODULE}.policy_repository.bulk_remove_policies",
        new_callable=AsyncMock, side_effect=_fake_bulk_policy_result,
    )

    body = BulkPolicyRequest(items=[
        BulkPolicyItem(user_email=system_user.email, policy_name=policy.name),
        BulkPolicyItem(user_email=normal_user.email, policy_name=policy.name),
    ])

    result = await bulk_remove_policies(body, MagicMock(), current_user=CALLER, db=MagicMock())

    statuses = {r.user_email: (r.status, r.error) for r in result.results}
    assert statuses[system_user.email] == ("error", "SYSTEM_USER_CANNOT_BE_MODIFIED")
    assert statuses[normal_user.email] == ("success", None)
    (valid_items_arg, *_rest), _kwargs = bulk_remove_mock.call_args
    assert [user.email for user, _p in valid_items_arg] == [normal_user.email]
