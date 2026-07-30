# tests/backend/app/access/test_scope_unit.py
#
# Pure unit coverage for app/access/scope.py's get_company_scope. No DB, no
# app, just Policy objects in and a CompanyScope out, mirroring how
# mystic_auth's own policy_evaluator is unit-tested (Policy objects in, bool
# out, no DB dependency).
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from backend.app.access.scope import get_company_scope

MODULE = "backend.app.access.scope"


def _policy(actions, resource_type="*", conditions=None):
    return SimpleNamespace(actions=actions, resource_type=resource_type, conditions=conditions)


@pytest.mark.asyncio
async def test_unrestricted_when_a_matching_policy_has_no_conditions(mocker):
    mocker.patch(
        f"{MODULE}.policy_repository.get_active_policies_for_user",
        new=AsyncMock(return_value=[_policy(["company:read"], conditions=None)]),
    )

    scope = await get_company_scope("user@example.com", "company:read", "company", db=object())

    assert scope.unrestricted is True
    assert scope.company_ids == frozenset()
    assert scope.group_root_ids == frozenset()
    assert scope.is_empty() is False


@pytest.mark.asyncio
async def test_company_id_condition_scopes_to_exactly_that_company(mocker):
    mocker.patch(
        f"{MODULE}.policy_repository.get_active_policies_for_user",
        new=AsyncMock(
            return_value=[_policy(["company:read"], conditions={"resource_attributes": {"company_id": 42}})]
        ),
    )

    scope = await get_company_scope("user@example.com", "company:read", "company", db=object())

    assert scope.unrestricted is False
    assert scope.company_ids == frozenset({42})
    assert scope.group_root_ids == frozenset()


@pytest.mark.asyncio
async def test_group_root_id_condition_scopes_to_the_whole_group(mocker):
    mocker.patch(
        f"{MODULE}.policy_repository.get_active_policies_for_user",
        new=AsyncMock(
            return_value=[_policy(["company:read"], conditions={"resource_attributes": {"group_root_id": 7}})]
        ),
    )

    scope = await get_company_scope("user@example.com", "company:read", "company", db=object())

    assert scope.unrestricted is False
    assert scope.group_root_ids == frozenset({7})


@pytest.mark.asyncio
async def test_policy_for_a_different_action_is_ignored(mocker):
    mocker.patch(
        f"{MODULE}.policy_repository.get_active_policies_for_user",
        new=AsyncMock(return_value=[_policy(["company:create"], conditions=None)]),
    )

    scope = await get_company_scope("user@example.com", "company:read", "company", db=object())

    assert scope.is_empty() is True


@pytest.mark.asyncio
async def test_policy_for_a_different_resource_type_is_ignored(mocker):
    mocker.patch(
        f"{MODULE}.policy_repository.get_active_policies_for_user",
        new=AsyncMock(return_value=[_policy(["company:read"], resource_type="balance_sheet", conditions=None)]),
    )

    scope = await get_company_scope("user@example.com", "company:read", "company", db=object())

    assert scope.is_empty() is True


@pytest.mark.asyncio
async def test_no_policies_at_all_yields_empty_scope(mocker):
    mocker.patch(
        f"{MODULE}.policy_repository.get_active_policies_for_user",
        new=AsyncMock(return_value=[]),
    )

    scope = await get_company_scope("user@example.com", "company:read", "company", db=object())

    assert scope.is_empty() is True
