# log_and_notify_bulk_success is the shared tail of every bulk PBAC route:
# audit-log every successful item, then notify each affected user once (not
# once per item) that their permissions changed. Covers deduping repeated
# user_emails in one batch, and only notifying on success.
from unittest.mock import AsyncMock

import pytest

from backend.mystic_auth.authorization.schemas.bulk_schema import BulkItemResult
from backend.mystic_auth.authorization.services.bulk_notification import (
    log_and_notify_bulk_success,
)

MODULE = "backend.mystic_auth.authorization.services.bulk_notification"


@pytest.mark.asyncio
async def test_notifies_each_affected_user_only_once_even_with_repeated_items(mocker):
    """Two successful items for the same user (e.g. two policies assigned
    to the same email in one batch) must only fire one permissions-changed
    notification for that user, not two."""
    log_mock = mocker.patch(f"{MODULE}.log_security_event", new_callable=AsyncMock)
    notify_mock = mocker.patch(f"{MODULE}.publish_permissions_changed", new_callable=AsyncMock)

    results = [
        BulkItemResult(user_email="a@example.com", identifier="policy_one", status="success"),
        BulkItemResult(user_email="a@example.com", identifier="policy_two", status="success"),
        BulkItemResult(user_email="b@example.com", identifier="policy_three", status="success"),
    ]

    await log_and_notify_bulk_success(
        results, "policy.assigned", db=None,
        actor_email="admin@example.com", actor_field="assigned_by", identifier_field="policy_name",
    )

    assert log_mock.await_count == 3
    assert {call.args[0] for call in notify_mock.await_args_list} == {"a@example.com", "b@example.com"}
    assert notify_mock.await_count == 2


@pytest.mark.asyncio
async def test_only_successful_items_are_logged_or_notified(mocker):
    log_mock = mocker.patch(f"{MODULE}.log_security_event", new_callable=AsyncMock)
    notify_mock = mocker.patch(f"{MODULE}.publish_permissions_changed", new_callable=AsyncMock)

    results = [
        BulkItemResult(user_email="a@example.com", identifier="policy_one", status="error", error="USER_NOT_FOUND"),
        BulkItemResult(user_email="b@example.com", identifier="policy_two", status="already_held"),
    ]

    await log_and_notify_bulk_success(
        results, "policy.assigned", db=None,
        actor_email="admin@example.com", actor_field="assigned_by", identifier_field="policy_name",
    )

    log_mock.assert_not_called()
    notify_mock.assert_not_called()


@pytest.mark.asyncio
async def test_notify_permissions_changed_can_be_disabled(mocker):
    """bulk_role_routes.py's role field is display-only metadata, not a PBAC
    grant: it never fires the permissions-changed nudge."""
    log_mock = mocker.patch(f"{MODULE}.log_security_event", new_callable=AsyncMock)
    notify_mock = mocker.patch(f"{MODULE}.publish_permissions_changed", new_callable=AsyncMock)

    results = [BulkItemResult(user_email="a@example.com", identifier="admin", status="success")]

    await log_and_notify_bulk_success(
        results, "user.role_changed", db=None,
        actor_email="admin@example.com", actor_field="changed_by", identifier_field="new_role",
        notify_permissions_changed=False,
    )

    log_mock.assert_awaited_once()
    notify_mock.assert_not_called()
