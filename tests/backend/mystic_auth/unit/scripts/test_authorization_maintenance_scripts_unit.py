from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from backend.mystic_auth.scripts import (
    invalidate_authorization_cache as invalidate_script,
)
from backend.mystic_auth.scripts import (
    report_conditioned_grant_conflicts as report_script,
)


@pytest.mark.asyncio
async def test_invalidate_cache_deduplicates_emails_and_flushes_all_when_requested(mocker, capsys):
    policies = mocker.patch.object(
        invalidate_script.authorization_cache_service,
        "invalidate_user_policies_bulk",
        new_callable=AsyncMock,
    )
    permissions = mocker.patch.object(
        invalidate_script.authorization_cache_service,
        "invalidate_user_permissions_bulk",
        new_callable=AsyncMock,
    )
    all_policies = mocker.patch.object(
        invalidate_script.authorization_cache_service,
        "invalidate_all_user_policies",
        new_callable=AsyncMock,
    )

    await invalidate_script._invalidate(["a@example.com", "a@example.com", "b@example.com"], True)

    expected = {"a@example.com", "b@example.com"}
    policies.assert_awaited_once_with(expected)
    permissions.assert_awaited_once_with(expected)
    all_policies.assert_awaited_once_with()
    assert "2 user(s)" in capsys.readouterr().out


@pytest.mark.asyncio
async def test_invalidate_cache_without_options_is_a_safe_noop(capsys):
    await invalidate_script._invalidate([], False)

    assert "Nothing to do" in capsys.readouterr().out


def test_invalidate_cache_cli_parses_repeatable_email_and_all_policy_flag(mocker):
    run = mocker.patch.object(invalidate_script.asyncio, "run")
    mocker.patch("sys.argv", ["invalidate", "--email", "a@example.com", "--email", "b@example.com", "--all-policies"])

    invalidate_script.main()

    run.assert_called_once()
    run.call_args.args[0].close()


@pytest.mark.asyncio
async def test_users_with_any_grant_returns_sorted_distinct_emails(mocker):
    policy_result = SimpleNamespace(scalars=lambda: iter(["b@example.com", "a@example.com"]))
    permission_result = SimpleNamespace(scalars=lambda: iter(["a@example.com", "c@example.com"]))
    db = SimpleNamespace(execute=AsyncMock(side_effect=[policy_result, permission_result]))

    emails = await report_script._users_with_any_grant(db)

    assert emails == ["a@example.com", "b@example.com", "c@example.com"]
    assert db.execute.await_count == 2


@pytest.mark.asyncio
async def test_report_finds_only_same_action_conditioned_and_unconditioned_pairs(mocker):
    grants = [
        SimpleNamespace(name="time-limited", actions=["reports:read"], resource_type="reports", conditions={"hours": 2}),
        SimpleNamespace(name="broad-access", actions=["reports:read"], resource_type="reports", conditions=None),
        SimpleNamespace(name="other-resource", actions=["reports:read"], resource_type="users", conditions=None),
        SimpleNamespace(name="other-action", actions=["users:read"], resource_type="reports", conditions={"team": "x"}),
    ]

    async def get_session():
        yield object()

    mocker.patch.object(report_script.database, "get_session", side_effect=get_session)
    mocker.patch.object(report_script, "_users_with_any_grant", new_callable=AsyncMock, return_value=["a@example.com"])
    mocker.patch.object(report_script.AuthorizationService, "_get_effective_policies", new_callable=AsyncMock, return_value=grants)

    assert await report_script._report() == [{
        "user_email": "a@example.com",
        "action": "reports:read",
        "resource_type": "reports",
        "sources": ["time-limited", "broad-access"],
    }]


@pytest.mark.asyncio
async def test_report_returns_empty_when_database_has_no_grants(mocker):
    async def get_session():
        yield object()

    mocker.patch.object(report_script.database, "get_session", side_effect=get_session)
    mocker.patch.object(report_script, "_users_with_any_grant", new_callable=AsyncMock, return_value=[])
    effective = mocker.patch.object(report_script.AuthorizationService, "_get_effective_policies", new_callable=AsyncMock)

    assert await report_script._report() == []
    effective.assert_not_awaited()


def test_report_cli_prints_findings_and_explanation(mocker, capsys):
    real_run = report_script.asyncio.run
    async def findings():
        return [{"user_email": "a@example.com", "action": "reports:read", "resource_type": "reports", "sources": ["limited", "broad"]}]

    mocker.patch.object(report_script, "_report", side_effect=findings)
    mocker.patch.object(report_script.asyncio, "run", side_effect=real_run)

    report_script.main()

    output = capsys.readouterr().out
    assert "Found 1 conditioned/unconditioned grant conflict" in output
    assert "a@example.com" in output
    assert "conditioned grant's restriction is not actually in effect" in output


def test_report_cli_explains_empty_result(mocker, capsys):
    real_run = report_script.asyncio.run
    async def findings():
        return []

    mocker.patch.object(report_script, "_report", side_effect=findings)
    mocker.patch.object(report_script.asyncio, "run", side_effect=real_run)

    report_script.main()

    assert "No conflicts found" in capsys.readouterr().out
