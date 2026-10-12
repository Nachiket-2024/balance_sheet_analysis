# Unit coverage for AuthorizationService._get_effective_policies: a direct
# UserPermission grant must be normalized into a transient, single-action
# Policy-shaped object and combined with the user's real assigned policies
# before evaluation (this lets it reuse PolicyEvaluationEngine unchanged
# instead of a parallel evaluation path). conftest.py in this directory stubs
# the direct-grants fetch to "none" by default; these tests override it.
from unittest.mock import AsyncMock

import pytest

from backend.mystic_auth.authorization.models.policy_model import Policy
from backend.mystic_auth.authorization.models.user_permission_model import (
    UserPermission,
)
from backend.mystic_auth.authorization.services.authorization_service import (
    authorization_service,
)

MODULE = "backend.mystic_auth.authorization.services.authorization_service"


def _grant(action, resource_type="users", conditions=None):
    return UserPermission(action=action, resource_type=resource_type, conditions=conditions, is_active=True)


@pytest.mark.asyncio
async def test_a_direct_grant_alone_authorizes_the_action_with_no_policy_held(mocker):
    mocker.patch(f"{MODULE}.policy_repository.get_active_policies_for_user", new_callable=AsyncMock, return_value=[])
    mocker.patch(
        f"{MODULE}.user_permission_repository.get_active_permissions_for_user",
        new_callable=AsyncMock,
        return_value=[_grant("users:list_all")],
    )

    result = await authorization_service.authorize("user@example.com", "users:list_all", "users", db=None)

    assert result is True


@pytest.mark.asyncio
async def test_a_direct_grant_for_a_different_action_does_not_authorize(mocker):
    mocker.patch(f"{MODULE}.policy_repository.get_active_policies_for_user", new_callable=AsyncMock, return_value=[])
    mocker.patch(
        f"{MODULE}.user_permission_repository.get_active_permissions_for_user",
        new_callable=AsyncMock,
        return_value=[_grant("users:read_own")],
    )

    result = await authorization_service.authorize("user@example.com", "users:list_all", "users", db=None)

    assert result is False


@pytest.mark.asyncio
async def test_direct_grant_conditions_are_evaluated_the_same_way_a_policys_are(mocker):
    """Reuses the same conditions mechanism as Policy.conditions, not a second,
    weaker one: a self_only-scoped direct grant behaves identically to a
    self_only-scoped policy."""
    mocker.patch(f"{MODULE}.policy_repository.get_active_policies_for_user", new_callable=AsyncMock, return_value=[])
    mocker.patch(
        f"{MODULE}.user_permission_repository.get_active_permissions_for_user",
        new_callable=AsyncMock,
        return_value=[_grant("documents:read", resource_type="documents", conditions={"self_only": True})],
    )

    owned = await authorization_service.authorize(
        "user@example.com", "documents:read", "documents", db=None, resource={"email": "user@example.com"}
    )
    not_owned = await authorization_service.authorize(
        "user@example.com", "documents:read", "documents", db=None, resource={"email": "someone-else@example.com"}
    )

    assert owned is True
    assert not_owned is False


@pytest.mark.asyncio
async def test_a_direct_grant_and_a_policy_both_contribute_to_the_same_decision(mocker):
    """OR across grants, same as OR across policies: a user can be authorized
    by their assigned policy for one action and a direct grant for another,
    evaluated together in one decision."""
    mocker.patch(
        f"{MODULE}.policy_repository.get_active_policies_for_user",
        new_callable=AsyncMock,
        return_value=[Policy(name="self_service", actions=["users:read_own"], resource_type="users", is_active=True)],
    )
    mocker.patch(
        f"{MODULE}.user_permission_repository.get_active_permissions_for_user",
        new_callable=AsyncMock,
        return_value=[_grant("users:list_all")],
    )

    decision = await authorization_service.authorize_detailed("user@example.com", "users:list_all", "users", db=None)

    assert decision.allowed is True
    # The synthetic policy's name carries the "direct:" prefix so a
    # matched/rejected policy name is distinguishable from a real,
    # user-authored policy with no schema change.
    assert decision.matched_policies == ["direct:users:list_all"]


@pytest.mark.asyncio
async def test_authorize_batch_combines_direct_grants_with_policies_for_every_check(mocker):
    """authorize_batch shares the same _get_effective_policies helper as
    authorize_detailed: a direct grant must be visible to every check in the
    batch, fetched once, not per-check."""
    mocker.patch(f"{MODULE}.policy_repository.get_active_policies_for_user", new_callable=AsyncMock, return_value=[])
    permissions_mock = mocker.patch(
        f"{MODULE}.user_permission_repository.get_active_permissions_for_user",
        new_callable=AsyncMock,
        return_value=[_grant("users:list_all")],
    )
    mocker.patch(f"{MODULE}.authorization_audit_log_repository.create_entries", new_callable=AsyncMock)

    decisions = await authorization_service.authorize_batch(
        "user@example.com",
        [
            {"action": "users:list_all", "resource_type": "users"},
            {"action": "users:delete_any", "resource_type": "users"},
        ],
        db=None,
    )

    assert [d.allowed for d in decisions] == [True, False]
    permissions_mock.assert_called_once()
