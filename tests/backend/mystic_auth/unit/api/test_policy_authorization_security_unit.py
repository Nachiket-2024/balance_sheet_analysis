# tests/backend/mystic_auth/unit/test_policy_authorization_security_unit.py
#
# Security-review coverage (claude.md's "Authorization Security Review"):
# policy create/update/assign must never let a caller grant one of this
# app's own sensitive actions (Permission's fixed vocabulary) that they do
# not already hold themselves, baseline policies must be undeletable and
# unrenameable, and the last system_superuser assignment must be
# irrevocable, all traced to concrete privilege-escalation / lockout
# scenarios below.
from unittest.mock import AsyncMock, MagicMock

import pytest
from backend.mystic_auth.api.pbac_routes.policy_assignment_routes import (
    assign_policy_to_user,
    remove_policy_from_user,
)
from backend.mystic_auth.api.pbac_routes.policy_crud_routes import (
    create_policy,
    delete_policy,
    update_policy,
)
from backend.mystic_auth.authorization.policies.default_policies import SYSTEM_SUPERUSER_POLICY_NAME
from backend.mystic_auth.authorization.schemas.policy_schema import PolicyAssignmentRequest, PolicyCreate, PolicyUpdate
from backend.mystic_auth.authorization.services.authorization_service import AuthorizationService
from fastapi import HTTPException

SERVICE_MODULE = "backend.mystic_auth.authorization.services.authorization_service"
# create/update/delete_policy live in policy_crud_routes; assign/remove live
# in policy_assignment_routes: each mocker.patch target below must match
# whichever module actually imported the name being patched (see the PBAC
# route split in backend/mystic_auth/api/pbac_routes/).
ROUTES_MODULE = "backend.mystic_auth.api.pbac_routes.policy_crud_routes"
ASSIGNMENT_ROUTES_MODULE = "backend.mystic_auth.api.pbac_routes.policy_assignment_routes"

CALLER = {"email": "caller@example.com", "name": "Caller"}


def _make_policy(**overrides):
    policy = MagicMock()
    policy.id = 1
    policy.name = "some_policy"
    policy.description = "desc"
    policy.actions = ["users:read_own"]
    policy.resource_type = "users"
    policy.conditions = None
    policy.is_active = True
    for key, value in overrides.items():
        setattr(policy, key, value)
    return policy


# ==================================================================
# AuthorizationService.assert_authorized_to_grant
# ==================================================================

@pytest.mark.asyncio
async def test_assert_authorized_to_grant_passes_when_caller_holds_all_actions(mocker):
    mocker.patch(f"{SERVICE_MODULE}.AuthorizationService.authorize", new_callable=AsyncMock, return_value=True)

    await AuthorizationService.assert_authorized_to_grant(
        "caller@example.com", ["users:read_own", "users:update_own"], "users", "fake-db"
    )


@pytest.mark.asyncio
async def test_assert_authorized_to_grant_rejects_action_caller_lacks(mocker):
    mocker.patch(f"{SERVICE_MODULE}.AuthorizationService.authorize", new_callable=AsyncMock, return_value=False)

    with pytest.raises(HTTPException) as exc_info:
        await AuthorizationService.assert_authorized_to_grant(
            "caller@example.com", ["policies:delete"], "policies", "fake-db"
        )
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_assert_authorized_to_grant_ignores_actions_outside_the_app_own_vocabulary(mocker):
    """Arbitrary business-domain actions a downstream app defines for its
    own resources (e.g. "projects:read") are not this app's own sensitive
    actions (Permission's fixed vocabulary) and must not be gated: PBAC
    policy authoring is meant to freely grant whatever a real deployment
    needs for its own resources."""
    authorize_mock = mocker.patch(f"{SERVICE_MODULE}.AuthorizationService.authorize", new_callable=AsyncMock, return_value=False)

    await AuthorizationService.assert_authorized_to_grant(
        "caller@example.com", ["projects:read", "documents:publish"], "projects", "fake-db"
    )

    authorize_mock.assert_not_awaited()


# ==================================================================
# create_policy: cannot mint a policy more powerful than the caller
# ==================================================================

@pytest.mark.asyncio
async def test_create_policy_blocks_minting_action_caller_does_not_hold(mocker):
    """Holding only policies:create (the dependency already satisfied to
    reach this handler) must not be enough to create a policy granting,
    say, users:purge unless the caller already has it."""
    policy_data = PolicyCreate(name="sneaky", actions=["users:purge"], resource_type="users")
    mocker.patch(f"{ROUTES_MODULE}.policy_repository.get_by_name", new_callable=AsyncMock, return_value=None)
    create_mock = mocker.patch(f"{ROUTES_MODULE}.policy_repository.create", new_callable=AsyncMock)
    mocker.patch(f"{SERVICE_MODULE}.AuthorizationService.authorize", new_callable=AsyncMock, return_value=False)

    with pytest.raises(HTTPException) as exc_info:
        await create_policy(policy_data, current_user=CALLER, db="fake-db")

    assert exc_info.value.status_code == 403
    create_mock.assert_not_called()


@pytest.mark.asyncio
async def test_create_policy_allows_when_caller_holds_every_action(mocker):
    policy_data = PolicyCreate(name="fine", actions=["users:read_own"], resource_type="users")
    created = _make_policy(name="fine")
    mocker.patch(f"{ROUTES_MODULE}.policy_repository.get_by_name", new_callable=AsyncMock, return_value=None)
    mocker.patch(f"{ROUTES_MODULE}.policy_repository.create", new_callable=AsyncMock, return_value=created)
    mocker.patch(f"{SERVICE_MODULE}.AuthorizationService.authorize", new_callable=AsyncMock, return_value=True)

    result = await create_policy(policy_data, current_user=CALLER, db="fake-db")

    assert result is created


@pytest.mark.asyncio
async def test_create_policy_allows_business_domain_actions_regardless_of_caller_holdings(mocker):
    """Pins the scoping decision: a caller with policies:create can create
    a policy for arbitrary downstream business actions (outside this app's
    own Permission vocabulary) even if authorize() would say no for them,
    the check must never even be consulted for such actions."""
    policy_data = PolicyCreate(name="app_policy", actions=["projects:read"], resource_type="projects")
    created = _make_policy(name="app_policy", actions=["projects:read"], resource_type="projects")
    mocker.patch(f"{ROUTES_MODULE}.policy_repository.get_by_name", new_callable=AsyncMock, return_value=None)
    mocker.patch(f"{ROUTES_MODULE}.policy_repository.create", new_callable=AsyncMock, return_value=created)
    authorize_mock = mocker.patch(f"{SERVICE_MODULE}.AuthorizationService.authorize", new_callable=AsyncMock, return_value=False)

    result = await create_policy(policy_data, current_user=CALLER, db="fake-db")

    assert result is created
    authorize_mock.assert_not_awaited()


# ==================================================================
# update_policy: cannot re-grant escalated actions, cannot rename baseline
# ==================================================================

@pytest.mark.asyncio
async def test_update_policy_blocks_adding_action_caller_does_not_hold(mocker):
    policy = _make_policy(name="some_policy", actions=["users:read_own"])
    update_data = PolicyUpdate(actions=["users:read_own", "policies:delete"])
    mocker.patch(f"{ROUTES_MODULE}.policy_repository.get_by_name", new_callable=AsyncMock, return_value=policy)
    update_mock = mocker.patch(f"{ROUTES_MODULE}.policy_repository.update", new_callable=AsyncMock)
    mocker.patch(f"{SERVICE_MODULE}.AuthorizationService.authorize", new_callable=AsyncMock, return_value=False)

    with pytest.raises(HTTPException) as exc_info:
        await update_policy("some_policy", update_data, current_user=CALLER, db="fake-db")

    assert exc_info.value.status_code == 403
    update_mock.assert_not_called()


@pytest.mark.asyncio
async def test_update_policy_allows_non_action_changes_without_grant_check(mocker):
    """Toggling is_active or editing description must not require the
    escalation check at all: only an `actions` change does."""
    policy = _make_policy(name="some_policy")
    update_data = PolicyUpdate(is_active=False)
    mocker.patch(f"{ROUTES_MODULE}.policy_repository.get_by_name", new_callable=AsyncMock, return_value=policy)
    update_mock = mocker.patch(f"{ROUTES_MODULE}.policy_repository.update", new_callable=AsyncMock, return_value=policy)
    authorize_mock = mocker.patch(f"{SERVICE_MODULE}.AuthorizationService.authorize", new_callable=AsyncMock, return_value=False)

    await update_policy("some_policy", update_data, current_user=CALLER, db="fake-db")

    authorize_mock.assert_not_awaited()
    update_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_policy_blocks_renaming_baseline_policy(mocker):
    policy = _make_policy(name=SYSTEM_SUPERUSER_POLICY_NAME)
    update_data = PolicyUpdate(name="renamed_superuser")
    mocker.patch(f"{ROUTES_MODULE}.policy_repository.get_by_name", new_callable=AsyncMock, return_value=policy)
    update_mock = mocker.patch(f"{ROUTES_MODULE}.policy_repository.update", new_callable=AsyncMock)

    with pytest.raises(HTTPException) as exc_info:
        await update_policy(SYSTEM_SUPERUSER_POLICY_NAME, update_data, current_user=CALLER, db="fake-db")

    assert exc_info.value.status_code == 403
    update_mock.assert_not_called()


# ==================================================================
# delete_policy: baseline policies are undeletable
# ==================================================================

@pytest.mark.asyncio
async def test_delete_policy_blocks_deleting_baseline_policy(mocker):
    policy = _make_policy(name=SYSTEM_SUPERUSER_POLICY_NAME)
    mocker.patch(f"{ROUTES_MODULE}.policy_repository.get_by_name", new_callable=AsyncMock, return_value=policy)
    delete_mock = mocker.patch(f"{ROUTES_MODULE}.policy_repository.delete", new_callable=AsyncMock)

    with pytest.raises(HTTPException) as exc_info:
        await delete_policy(SYSTEM_SUPERUSER_POLICY_NAME, reason=None, current_user=CALLER, db="fake-db")

    assert exc_info.value.status_code == 403
    delete_mock.assert_not_called()


@pytest.mark.asyncio
async def test_delete_policy_allows_deleting_non_baseline_policy(mocker):
    policy = _make_policy(name="custom_policy")
    mocker.patch(f"{ROUTES_MODULE}.policy_repository.get_by_name", new_callable=AsyncMock, return_value=policy)
    delete_mock = mocker.patch(f"{ROUTES_MODULE}.policy_repository.delete", new_callable=AsyncMock)

    await delete_policy("custom_policy", reason=None, current_user=CALLER, db="fake-db")

    delete_mock.assert_awaited_once()


# ==================================================================
# assign_policy_to_user: cannot hand out a more powerful policy than held
# ==================================================================

@pytest.mark.asyncio
async def test_assign_policy_blocks_self_escalation_to_superuser(mocker):
    """The canonical escalation attempt: a caller holding only
    policies:assign tries to assign themselves system_superuser, which
    they do not otherwise hold."""
    target_user = MagicMock(id=2, email="caller@example.com")
    superuser_policy = _make_policy(
        name=SYSTEM_SUPERUSER_POLICY_NAME,
        actions=["users:assign_system_role", "users:purge", "policies:read"],
        resource_type="*",
    )
    mocker.patch(f"{ASSIGNMENT_ROUTES_MODULE}.user_crud.get_by_email", new_callable=AsyncMock, return_value=target_user)
    mocker.patch(f"{ASSIGNMENT_ROUTES_MODULE}.policy_repository.get_by_name", new_callable=AsyncMock, return_value=superuser_policy)
    assign_mock = mocker.patch(f"{ASSIGNMENT_ROUTES_MODULE}.policy_repository.assign_policy_to_user", new_callable=AsyncMock)
    mocker.patch(f"{SERVICE_MODULE}.AuthorizationService.authorize", new_callable=AsyncMock, return_value=False)

    with pytest.raises(HTTPException) as exc_info:
        await assign_policy_to_user(
            "caller@example.com",
            PolicyAssignmentRequest(policy_name=SYSTEM_SUPERUSER_POLICY_NAME),
            current_user=CALLER, db="fake-db",
        )

    assert exc_info.value.status_code == 403
    assign_mock.assert_not_called()


@pytest.mark.asyncio
async def test_assign_policy_allows_when_caller_already_holds_every_action(mocker):
    target_user = MagicMock(id=2, email="someone@example.com")
    policy = _make_policy(name="self_service", actions=["users:read_own"])
    mocker.patch(f"{ASSIGNMENT_ROUTES_MODULE}.user_crud.get_by_email", new_callable=AsyncMock, return_value=target_user)
    mocker.patch(f"{ASSIGNMENT_ROUTES_MODULE}.policy_repository.get_by_name", new_callable=AsyncMock, return_value=policy)
    assign_mock = mocker.patch(f"{ASSIGNMENT_ROUTES_MODULE}.policy_repository.assign_policy_to_user", new_callable=AsyncMock)
    mocker.patch(f"{SERVICE_MODULE}.AuthorizationService.authorize", new_callable=AsyncMock, return_value=True)

    await assign_policy_to_user(
        "someone@example.com", PolicyAssignmentRequest(policy_name="self_service"),
        current_user=CALLER, db="fake-db",
    )

    assign_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_assign_policy_allows_business_domain_policy_regardless_of_caller_holdings(mocker):
    target_user = MagicMock(id=2, email="someone@example.com")
    app_policy = _make_policy(name="app_policy", actions=["projects:read"], resource_type="projects")
    mocker.patch(f"{ASSIGNMENT_ROUTES_MODULE}.user_crud.get_by_email", new_callable=AsyncMock, return_value=target_user)
    mocker.patch(f"{ASSIGNMENT_ROUTES_MODULE}.policy_repository.get_by_name", new_callable=AsyncMock, return_value=app_policy)
    assign_mock = mocker.patch(f"{ASSIGNMENT_ROUTES_MODULE}.policy_repository.assign_policy_to_user", new_callable=AsyncMock)
    authorize_mock = mocker.patch(f"{SERVICE_MODULE}.AuthorizationService.authorize", new_callable=AsyncMock, return_value=False)

    await assign_policy_to_user(
        "someone@example.com", PolicyAssignmentRequest(policy_name="app_policy"),
        current_user=CALLER, db="fake-db",
    )

    authorize_mock.assert_not_awaited()
    assign_mock.assert_awaited_once()


# ==================================================================
# remove_policy_from_user: cannot strand the system with zero superusers
# ==================================================================

@pytest.mark.asyncio
async def test_remove_policy_blocks_removing_last_superuser_assignment(mocker):
    target_user = MagicMock(id=2, email="lastadmin@example.com")
    policy = _make_policy(name=SYSTEM_SUPERUSER_POLICY_NAME, id=7)
    mocker.patch(f"{ASSIGNMENT_ROUTES_MODULE}.user_crud.get_by_email", new_callable=AsyncMock, return_value=target_user)
    mocker.patch(f"{ASSIGNMENT_ROUTES_MODULE}.policy_repository.get_by_name", new_callable=AsyncMock, return_value=policy)
    mocker.patch(f"{ASSIGNMENT_ROUTES_MODULE}.policy_repository.count_assignments", new_callable=AsyncMock, return_value=1)
    remove_mock = mocker.patch(f"{ASSIGNMENT_ROUTES_MODULE}.policy_repository.remove_policy_from_user", new_callable=AsyncMock)

    with pytest.raises(HTTPException) as exc_info:
        await remove_policy_from_user(
            "lastadmin@example.com", SYSTEM_SUPERUSER_POLICY_NAME, current_user=CALLER, db="fake-db"
        )

    assert exc_info.value.status_code == 409
    remove_mock.assert_not_called()


@pytest.mark.asyncio
async def test_remove_policy_allows_when_other_superusers_remain(mocker):
    target_user = MagicMock(id=2, email="admin2@example.com")
    policy = _make_policy(name=SYSTEM_SUPERUSER_POLICY_NAME, id=7)
    mocker.patch(f"{ASSIGNMENT_ROUTES_MODULE}.user_crud.get_by_email", new_callable=AsyncMock, return_value=target_user)
    mocker.patch(f"{ASSIGNMENT_ROUTES_MODULE}.policy_repository.get_by_name", new_callable=AsyncMock, return_value=policy)
    mocker.patch(f"{ASSIGNMENT_ROUTES_MODULE}.policy_repository.count_assignments", new_callable=AsyncMock, return_value=2)
    remove_mock = mocker.patch(f"{ASSIGNMENT_ROUTES_MODULE}.policy_repository.remove_policy_from_user", new_callable=AsyncMock, return_value=True)

    await remove_policy_from_user(
        "admin2@example.com", SYSTEM_SUPERUSER_POLICY_NAME, current_user=CALLER, db="fake-db"
    )

    remove_mock.assert_awaited_once()
