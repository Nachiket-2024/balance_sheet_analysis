# tests/backend/mystic_auth/unit/test_user_policies_me_route_unit.py
#
# Unit coverage for GET /authorization/users/me/policies : the self-service
# "my own policy assignments" endpoint, added to support the frontend
# authorization service's getUserPolicies() (no policies:read required,
# mirroring GET /authorization/audit-log/me's own self-service rationale).
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from backend.mystic_auth.api.pbac_routes.policy_assignment_routes import list_my_policies

MODULE = "backend.mystic_auth.api.pbac_routes.policy_assignment_routes"


def _make_policy(name="self_service"):
    policy = MagicMock()
    policy.id = 1
    policy.name = name
    policy.description = "d"
    policy.actions = ["users:read_own"]
    policy.resource_type = "users"
    policy.conditions = None
    policy.is_active = True
    policy.created_at = datetime.now(UTC)
    policy.updated_at = datetime.now(UTC)
    policy.created_by = "system"
    return policy


@pytest.mark.asyncio
async def test_list_my_policies_scopes_to_caller_email(mocker):
    current_user = {"email": "caller@example.com", "name": "Caller"}
    expected_policies = [_make_policy("self_service"), _make_policy("user_administration")]
    get_policies_mock = mocker.patch(
        f"{MODULE}.policy_repository.get_policies_for_user", new_callable=AsyncMock, return_value=expected_policies
    )

    result = await list_my_policies(current_user=current_user, db="fake-db")

    get_policies_mock.assert_awaited_once_with("caller@example.com", "fake-db")
    assert result.user_email == "caller@example.com"
    assert {p.name for p in result.policies} == {"self_service", "user_administration"}


@pytest.mark.asyncio
async def test_list_my_policies_never_accepts_a_different_users_email(mocker):
    """There is no email parameter at all on this endpoint : it can only
    ever return the authenticated caller's own policies, never anyone
    else's, regardless of what a client might try to pass."""
    current_user = {"email": "someone@example.com", "name": "Someone"}
    get_policies_mock = mocker.patch(
        f"{MODULE}.policy_repository.get_policies_for_user", new_callable=AsyncMock, return_value=[]
    )

    result = await list_my_policies(current_user=current_user, db="fake-db")

    assert result.user_email == "someone@example.com"
    get_policies_mock.assert_awaited_once_with("someone@example.com", "fake-db")
