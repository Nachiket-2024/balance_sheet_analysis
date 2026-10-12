# Security coverage: assigning/removing a policy must never let a caller
# hand out (or strip) a sensitive action they don't already hold
# themselves, and the last system_superuser assignment must be
# irrevocable. Covers policy_assignment_routes.py (assign/remove); see
# test_policy_crud_authorization_security_unit.py for create/update/delete.
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from backend.mystic_auth.api.pbac_routes.policies.policy_assignment_routes import (
    assign_policy_to_user,
    remove_policy_from_user,
    revoke_policy_action_from_user,
)
from backend.mystic_auth.authorization.policies.default_policies import (
    SYSTEM_SUPERUSER_POLICY_NAME,
)
from backend.mystic_auth.authorization.schemas.policy_schema import (
    PolicyActionRevocationRequest,
    PolicyAssignmentRequest,
)
from backend.mystic_auth.authorization.services.policy_action_revocation_service import (
    ActionNotInPolicyError,
)

from .authorization_test_helpers import authorization_decision

SERVICE_MODULE = "backend.mystic_auth.authorization.services.authorization_service"
ASSIGNMENT_ROUTES_MODULE = "backend.mystic_auth.api.pbac_routes.policies.policy_assignment_routes"

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
# assign_policy_to_user: cannot hand out a more powerful policy than held
# ==================================================================

@pytest.mark.asyncio
async def test_assign_policy_blocks_self_escalation_to_superuser(mocker):
    """A caller holding only policies:assign tries to assign themselves
    system_superuser, which they do not otherwise hold."""
    target_user = MagicMock(id=2, email="caller@example.com")
    superuser_policy = _make_policy(
        name=SYSTEM_SUPERUSER_POLICY_NAME,
        actions=["users:assign_system_role", "users:delete_any", "policies:read"],
        resource_type="*",
    )
    mocker.patch(f"{ASSIGNMENT_ROUTES_MODULE}.user_crud.get_by_email", new_callable=AsyncMock, return_value=target_user)
    mocker.patch(f"{ASSIGNMENT_ROUTES_MODULE}.policy_repository.get_by_name", new_callable=AsyncMock, return_value=superuser_policy)
    assign_mock = mocker.patch(f"{ASSIGNMENT_ROUTES_MODULE}.policy_repository.assign_policy_to_user", new_callable=AsyncMock)
    mocker.patch(f"{SERVICE_MODULE}.AuthorizationService.authorize_with_decision", new_callable=AsyncMock, return_value=authorization_decision(False))

    with pytest.raises(HTTPException) as exc_info:
        await assign_policy_to_user(
            "caller@example.com",
            PolicyAssignmentRequest(policy_name=SYSTEM_SUPERUSER_POLICY_NAME),
            request=MagicMock(),
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
    mocker.patch(f"{SERVICE_MODULE}.AuthorizationService.authorize_with_decision", new_callable=AsyncMock, return_value=authorization_decision(True))

    await assign_policy_to_user(
        "someone@example.com", PolicyAssignmentRequest(policy_name="self_service"),
        request=MagicMock(),
        current_user=CALLER, db="fake-db",
    )

    assign_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_assign_policy_blocks_unheld_business_domain_policy(mocker):
    target_user = MagicMock(id=2, email="someone@example.com")
    app_policy = _make_policy(name="app_policy", actions=["projects:read"], resource_type="projects")
    mocker.patch(f"{ASSIGNMENT_ROUTES_MODULE}.user_crud.get_by_email", new_callable=AsyncMock, return_value=target_user)
    mocker.patch(f"{ASSIGNMENT_ROUTES_MODULE}.policy_repository.get_by_name", new_callable=AsyncMock, return_value=app_policy)
    assign_mock = mocker.patch(f"{ASSIGNMENT_ROUTES_MODULE}.policy_repository.assign_policy_to_user", new_callable=AsyncMock)
    authorize_mock = mocker.patch(f"{SERVICE_MODULE}.AuthorizationService.authorize_with_decision", new_callable=AsyncMock, return_value=authorization_decision(False))
    mocker.patch(
        "backend.mystic_auth.authorization.services.authorization_grant_guard.policy_assignment_repository.get_active_policies_for_user",
        new_callable=AsyncMock,
        return_value=[],
    )

    with pytest.raises(HTTPException) as exc_info:
        await assign_policy_to_user(
            "someone@example.com", PolicyAssignmentRequest(policy_name="app_policy"),
            request=MagicMock(),
            current_user=CALLER, db="fake-db",
        )

    assert exc_info.value.status_code == 403
    authorize_mock.assert_awaited_once()
    assign_mock.assert_not_awaited()


# ==================================================================
# remove_policy_from_user: cannot strand the system with zero superusers
# ==================================================================

@pytest.mark.asyncio
async def test_remove_policy_blocks_when_caller_lacks_current_actions(mocker):
    """Without holding what's being revoked, bare policies:revoke could
    strip an equally- or more-privileged peer's access, including
    system_superuser itself."""
    target_user = MagicMock(id=2, email="someone@example.com")
    policy = _make_policy(name="custom_policy", actions=["users:delete_any"], resource_type="users")
    mocker.patch(f"{ASSIGNMENT_ROUTES_MODULE}.user_crud.get_by_email", new_callable=AsyncMock, return_value=target_user)
    mocker.patch(f"{ASSIGNMENT_ROUTES_MODULE}.policy_repository.get_by_name", new_callable=AsyncMock, return_value=policy)
    remove_mock = mocker.patch(f"{ASSIGNMENT_ROUTES_MODULE}.policy_repository.remove_policy_from_user", new_callable=AsyncMock)
    mocker.patch(f"{SERVICE_MODULE}.AuthorizationService.authorize_with_decision", new_callable=AsyncMock, return_value=authorization_decision(False))

    with pytest.raises(HTTPException) as exc_info:
        await remove_policy_from_user(
            "someone@example.com", "custom_policy", request=MagicMock(), current_user=CALLER, db="fake-db"
        )

    assert exc_info.value.status_code == 403
    remove_mock.assert_not_called()


@pytest.mark.asyncio
async def test_remove_policy_blocks_removing_last_superuser_assignment(mocker):
    target_user = MagicMock(id=2, email="lastadmin@example.com")
    policy = _make_policy(name=SYSTEM_SUPERUSER_POLICY_NAME, id=7)
    mocker.patch(f"{ASSIGNMENT_ROUTES_MODULE}.user_crud.get_by_email", new_callable=AsyncMock, return_value=target_user)
    mocker.patch(f"{ASSIGNMENT_ROUTES_MODULE}.policy_repository.get_by_name", new_callable=AsyncMock, return_value=policy)
    mocker.patch(f"{ASSIGNMENT_ROUTES_MODULE}.policy_repository.user_holds_policy", new_callable=AsyncMock, return_value=True)
    mocker.patch(f"{ASSIGNMENT_ROUTES_MODULE}.policy_repository.count_assignments", new_callable=AsyncMock, return_value=1)
    remove_mock = mocker.patch(f"{ASSIGNMENT_ROUTES_MODULE}.policy_repository.remove_policy_from_user", new_callable=AsyncMock)
    mocker.patch(f"{SERVICE_MODULE}.AuthorizationService.authorize_with_decision", new_callable=AsyncMock, return_value=authorization_decision(True))

    with pytest.raises(HTTPException) as exc_info:
        await remove_policy_from_user(
            "lastadmin@example.com", SYSTEM_SUPERUSER_POLICY_NAME, request=MagicMock(), current_user=CALLER, db="fake-db"
        )

    assert exc_info.value.status_code == 409
    remove_mock.assert_not_called()


@pytest.mark.asyncio
async def test_remove_policy_allows_when_other_superusers_remain(mocker):
    target_user = MagicMock(id=2, email="admin2@example.com")
    policy = _make_policy(name=SYSTEM_SUPERUSER_POLICY_NAME, id=7)
    mocker.patch(f"{ASSIGNMENT_ROUTES_MODULE}.user_crud.get_by_email", new_callable=AsyncMock, return_value=target_user)
    mocker.patch(f"{ASSIGNMENT_ROUTES_MODULE}.policy_repository.get_by_name", new_callable=AsyncMock, return_value=policy)
    mocker.patch(f"{ASSIGNMENT_ROUTES_MODULE}.policy_repository.user_holds_policy", new_callable=AsyncMock, return_value=True)
    mocker.patch(f"{ASSIGNMENT_ROUTES_MODULE}.policy_repository.count_assignments", new_callable=AsyncMock, return_value=2)
    remove_mock = mocker.patch(f"{ASSIGNMENT_ROUTES_MODULE}.policy_repository.remove_policy_from_user", new_callable=AsyncMock, return_value=True)
    mocker.patch(f"{SERVICE_MODULE}.AuthorizationService.authorize_with_decision", new_callable=AsyncMock, return_value=authorization_decision(True))

    await remove_policy_from_user(
        "admin2@example.com", SYSTEM_SUPERUSER_POLICY_NAME, request=MagicMock(), current_user=CALLER, db="fake-db"
    )

    remove_mock.assert_awaited_once()


# ==================================================================
# revoke_policy_action_from_user: same guards as remove_policy_from_user,
# since it also ends the user's policy assignment (converting the rest to
# direct grants). See policy_action_revocation_service.py.
# ==================================================================

@pytest.mark.asyncio
async def test_revoke_policy_action_blocks_when_caller_lacks_current_actions(mocker):
    """Same gap remove_policy_from_user's guard closes: without holding
    the policy's full action set, bare policies:revoke +
    permissions:grant could still strip a more-privileged peer's access
    via this route."""
    target_user = MagicMock(id=2, email="someone@example.com")
    policy = _make_policy(name="custom_policy", actions=["users:delete_any"], resource_type="users")
    mocker.patch(f"{ASSIGNMENT_ROUTES_MODULE}.user_crud.get_by_email", new_callable=AsyncMock, return_value=target_user)
    mocker.patch(f"{ASSIGNMENT_ROUTES_MODULE}.policy_repository.get_by_name", new_callable=AsyncMock, return_value=policy)
    revoke_mock = mocker.patch(
        f"{ASSIGNMENT_ROUTES_MODULE}.policy_action_revocation_service.revoke_single_action", new_callable=AsyncMock
    )
    mocker.patch(f"{SERVICE_MODULE}.AuthorizationService.authorize_with_decision", new_callable=AsyncMock, return_value=authorization_decision(False))

    with pytest.raises(HTTPException) as exc_info:
        await revoke_policy_action_from_user(
            "someone@example.com", "custom_policy",
            PolicyActionRevocationRequest(action="users:delete_any"),
            request=MagicMock(), current_user=CALLER, _permissions_grant=CALLER, db="fake-db",
        )

    assert exc_info.value.status_code == 403
    revoke_mock.assert_not_called()


@pytest.mark.asyncio
async def test_revoke_policy_action_blocks_last_superuser_assignment(mocker):
    target_user = MagicMock(id=2, email="lastadmin@example.com")
    policy = _make_policy(name=SYSTEM_SUPERUSER_POLICY_NAME, id=7, actions=["users:delete_any", "policies:read"])
    mocker.patch(f"{ASSIGNMENT_ROUTES_MODULE}.user_crud.get_by_email", new_callable=AsyncMock, return_value=target_user)
    mocker.patch(f"{ASSIGNMENT_ROUTES_MODULE}.policy_repository.get_by_name", new_callable=AsyncMock, return_value=policy)
    mocker.patch(f"{ASSIGNMENT_ROUTES_MODULE}.policy_repository.user_holds_policy", new_callable=AsyncMock, return_value=True)
    mocker.patch(f"{ASSIGNMENT_ROUTES_MODULE}.policy_repository.count_assignments", new_callable=AsyncMock, return_value=1)
    revoke_mock = mocker.patch(
        f"{ASSIGNMENT_ROUTES_MODULE}.policy_action_revocation_service.revoke_single_action", new_callable=AsyncMock
    )
    mocker.patch(f"{SERVICE_MODULE}.AuthorizationService.authorize_with_decision", new_callable=AsyncMock, return_value=authorization_decision(True))

    with pytest.raises(HTTPException) as exc_info:
        await revoke_policy_action_from_user(
            "lastadmin@example.com", SYSTEM_SUPERUSER_POLICY_NAME,
            PolicyActionRevocationRequest(action="users:delete_any"),
            request=MagicMock(), current_user=CALLER, _permissions_grant=CALLER, db="fake-db",
        )

    assert exc_info.value.status_code == 409
    revoke_mock.assert_not_called()


@pytest.mark.asyncio
async def test_revoke_policy_action_allows_when_other_superusers_remain(mocker):
    target_user = MagicMock(id=2, email="admin2@example.com")
    policy = _make_policy(name=SYSTEM_SUPERUSER_POLICY_NAME, id=7, actions=["users:delete_any", "policies:read"])
    mocker.patch(f"{ASSIGNMENT_ROUTES_MODULE}.user_crud.get_by_email", new_callable=AsyncMock, return_value=target_user)
    mocker.patch(f"{ASSIGNMENT_ROUTES_MODULE}.policy_repository.get_by_name", new_callable=AsyncMock, return_value=policy)
    mocker.patch(f"{ASSIGNMENT_ROUTES_MODULE}.policy_repository.user_holds_policy", new_callable=AsyncMock, return_value=True)
    mocker.patch(f"{ASSIGNMENT_ROUTES_MODULE}.policy_repository.count_assignments", new_callable=AsyncMock, return_value=2)
    revoke_mock = mocker.patch(
        f"{ASSIGNMENT_ROUTES_MODULE}.policy_action_revocation_service.revoke_single_action",
        new_callable=AsyncMock, return_value=True,
    )
    mocker.patch(f"{SERVICE_MODULE}.AuthorizationService.authorize_with_decision", new_callable=AsyncMock, return_value=authorization_decision(True))

    await revoke_policy_action_from_user(
        "admin2@example.com", SYSTEM_SUPERUSER_POLICY_NAME,
        PolicyActionRevocationRequest(action="users:delete_any"),
        request=MagicMock(), current_user=CALLER, _permissions_grant=CALLER, db="fake-db",
    )

    revoke_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_revoke_policy_action_rejects_action_not_in_policy(mocker):
    target_user = MagicMock(id=2, email="someone@example.com")
    policy = _make_policy(name="custom_policy", actions=["users:read_own"], resource_type="users")
    mocker.patch(f"{ASSIGNMENT_ROUTES_MODULE}.user_crud.get_by_email", new_callable=AsyncMock, return_value=target_user)
    mocker.patch(f"{ASSIGNMENT_ROUTES_MODULE}.policy_repository.get_by_name", new_callable=AsyncMock, return_value=policy)
    mocker.patch(f"{ASSIGNMENT_ROUTES_MODULE}.policy_repository.user_holds_policy", new_callable=AsyncMock, return_value=True)
    mocker.patch(
        f"{ASSIGNMENT_ROUTES_MODULE}.policy_action_revocation_service.revoke_single_action",
        new_callable=AsyncMock, side_effect=ActionNotInPolicyError("nope"),
    )
    mocker.patch(f"{SERVICE_MODULE}.AuthorizationService.authorize_with_decision", new_callable=AsyncMock, return_value=authorization_decision(True))

    with pytest.raises(HTTPException) as exc_info:
        await revoke_policy_action_from_user(
            "someone@example.com", "custom_policy",
            PolicyActionRevocationRequest(action="users:not_a_real_action"),
            request=MagicMock(), current_user=CALLER, _permissions_grant=CALLER, db="fake-db",
        )

    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_revoke_policy_action_404s_when_user_does_not_hold_policy(mocker):
    target_user = MagicMock(id=2, email="someone@example.com")
    policy = _make_policy(name="custom_policy", actions=["users:read_own"], resource_type="users")
    mocker.patch(f"{ASSIGNMENT_ROUTES_MODULE}.user_crud.get_by_email", new_callable=AsyncMock, return_value=target_user)
    mocker.patch(f"{ASSIGNMENT_ROUTES_MODULE}.policy_repository.get_by_name", new_callable=AsyncMock, return_value=policy)
    # The route's own holdership guard runs before the lockout check and
    # repository call, rather than letting revoke_single_action fall
    # through to a not-held return.
    mocker.patch(f"{ASSIGNMENT_ROUTES_MODULE}.policy_repository.user_holds_policy", new_callable=AsyncMock, return_value=False)
    revoke_mock = mocker.patch(
        f"{ASSIGNMENT_ROUTES_MODULE}.policy_action_revocation_service.revoke_single_action",
        new_callable=AsyncMock, return_value=False,
    )
    mocker.patch(f"{SERVICE_MODULE}.AuthorizationService.authorize_with_decision", new_callable=AsyncMock, return_value=authorization_decision(True))

    with pytest.raises(HTTPException) as exc_info:
        await revoke_policy_action_from_user(
            "someone@example.com", "custom_policy",
            PolicyActionRevocationRequest(action="users:read_own"),
            request=MagicMock(), current_user=CALLER, _permissions_grant=CALLER, db="fake-db",
        )

    assert exc_info.value.status_code == 404
    revoke_mock.assert_not_called()
