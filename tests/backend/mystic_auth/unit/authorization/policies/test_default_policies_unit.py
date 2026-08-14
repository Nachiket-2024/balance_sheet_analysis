# tests/backend/mystic_auth/unit/authorization/policies/test_default_policies_unit.py
from unittest.mock import AsyncMock

import pytest
from backend.mystic_auth.authorization.policies import default_policies

MODULE = "backend.mystic_auth.authorization.policies.default_policies"


class _FakePolicy:
    def __init__(self, id_):
        self.id = id_


@pytest.mark.asyncio
async def test_assign_app_default_policies_is_a_noop_when_unset(mocker):
    mocker.patch(f"{MODULE}.settings.DEFAULT_APP_POLICIES", "")
    get_by_name_mock = mocker.patch(f"{MODULE}.policy_repository.get_by_name", new_callable=AsyncMock)
    assign_mock = mocker.patch(f"{MODULE}.policy_repository.assign_policy_to_user", new_callable=AsyncMock)

    await default_policies.assign_app_default_policies(user_id=1, db=None)

    get_by_name_mock.assert_not_called()
    assign_mock.assert_not_called()


@pytest.mark.asyncio
async def test_assign_app_default_policies_assigns_every_configured_policy(mocker):
    mocker.patch(f"{MODULE}.settings.DEFAULT_APP_POLICIES", "extra_policy_one,extra_policy_two")
    mocker.patch(
        f"{MODULE}.policy_repository.get_by_name",
        new_callable=AsyncMock,
        side_effect=[_FakePolicy(10), _FakePolicy(20)],
    )
    assign_mock = mocker.patch(f"{MODULE}.policy_repository.assign_policy_to_user", new_callable=AsyncMock)

    await default_policies.assign_app_default_policies(user_id=1, db=None)

    assert assign_mock.await_count == 2
    assign_mock.assert_any_await(user_id=1, policy_id=10, db=None, assigned_by="system")
    assign_mock.assert_any_await(user_id=1, policy_id=20, db=None, assigned_by="system")


@pytest.mark.asyncio
async def test_assign_app_default_policies_skips_a_missing_policy_without_raising(mocker):
    # A misconfigured DEFAULT_APP_POLICIES name (policy not yet created) must
    # log, not raise: this runs inline in the verify/login request path, and
    # an operational misconfiguration shouldn't turn into a 500 for the user
    # completing an unrelated action.
    mocker.patch(f"{MODULE}.settings.DEFAULT_APP_POLICIES", "does_not_exist")
    mocker.patch(f"{MODULE}.policy_repository.get_by_name", new_callable=AsyncMock, return_value=None)
    assign_mock = mocker.patch(f"{MODULE}.policy_repository.assign_policy_to_user", new_callable=AsyncMock)

    await default_policies.assign_app_default_policies(user_id=1, db=None)

    assign_mock.assert_not_called()
