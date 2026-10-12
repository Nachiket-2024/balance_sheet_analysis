# tests/backend/mystic_auth/unit/user_lifecycle/test_user_purge_service_unit.py
#
# Mocked-collaborator coverage for purge_user_account's own wiring (revoke
# -> audit -> delete -> cache-invalidate sequence, and what it's called
# with), same split as test_account_purge_tasks_unit.py vs. the real-DB
# integration coverage. Specifically covers the authorization-cache
# invalidation this function used to skip entirely: without it, a fresh
# signup reusing a just-purged account's email within the cache's TTL
# window could transiently inherit that purged user's stale cached
# policies/permissions on its very first authorization check.
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.mystic_auth.user_lifecycle.user_purge_service import (
    AccountNoLongerEligibleForPurgeError,
    purge_user_account,
)

MODULE = "backend.mystic_auth.user_lifecycle.user_purge_service"

_DELETED_AT = datetime.now(UTC)


class _FakeUser:
    def __init__(self, email: str, id: int = 1, deleted_at=_DELETED_AT):
        self.id = id
        self.email = email
        self.deleted_at = deleted_at


@pytest.fixture(autouse=True)
def _mock_collaborators(mocker):
    mocker.patch(f"{MODULE}.refresh_token_service.revoke_all_tokens_for_user", new_callable=AsyncMock, return_value=2)
    mocker.patch(f"{MODULE}.log_security_event", new_callable=AsyncMock)
    mocker.patch(f"{MODULE}.user_crud.delete", new_callable=AsyncMock)
    # Purge also anonymizes the purged account's own audit-log rows (see
    # audit_log_repository.anonymize_for_user's docstring).
    # Mocked here by default like every other collaborator; dedicated
    # coverage for the call itself is below.
    mocker.patch(f"{MODULE}.audit_log_repository.anonymize_for_user", new_callable=AsyncMock, return_value=0)
    mocker.patch(f"{MODULE}.authorization_audit_log_repository.anonymize_for_user", new_callable=AsyncMock, return_value=0)
    # Default: the row lock re-read finds the account still soft-deleted,
    # i.e. the common case where nothing raced the purge. Individual tests
    # override this to exercise the race-guard path.
    mocker.patch(
        f"{MODULE}.user_crud.lock_by_id",
        new_callable=AsyncMock,
        side_effect=lambda user_id, db: _FakeUser("locked@example.com", id=user_id),
    )


@pytest.mark.asyncio
async def test_purge_invalidates_both_authorization_cache_entries_for_the_purged_users_email(mocker):
    invalidate_policies_mock = mocker.patch(
        f"{MODULE}.authorization_cache_service.invalidate_user_policies", new_callable=AsyncMock
    )
    invalidate_permissions_mock = mocker.patch(
        f"{MODULE}.authorization_cache_service.invalidate_user_permissions", new_callable=AsyncMock
    )
    user = _FakeUser("purge-me@example.com")

    await purge_user_account(user, db=MagicMock(), purged_by="admin@example.com")

    invalidate_policies_mock.assert_awaited_once_with("purge-me@example.com")
    invalidate_permissions_mock.assert_awaited_once_with("purge-me@example.com")


@pytest.mark.asyncio
async def test_purge_invalidates_the_cache_after_the_row_is_actually_deleted(mocker):
    """Ordering matters for the same reason the audit log is written before
    delete() here: the invalidation only needs to happen once the row (and
    the email it frees up) is actually gone, not before."""
    call_order = []
    mocker.patch(
        f"{MODULE}.user_crud.delete",
        new_callable=AsyncMock,
        side_effect=lambda **kwargs: call_order.append("delete"),
    )
    mocker.patch(
        f"{MODULE}.authorization_cache_service.invalidate_user_policies",
        new_callable=AsyncMock,
        side_effect=lambda *args: call_order.append("invalidate_policies"),
    )
    mocker.patch(
        f"{MODULE}.authorization_cache_service.invalidate_user_permissions",
        new_callable=AsyncMock,
        side_effect=lambda *args: call_order.append("invalidate_permissions"),
    )
    user = _FakeUser("order-check@example.com")

    await purge_user_account(user, db=MagicMock(), purged_by="admin@example.com")

    assert call_order == ["delete", "invalidate_policies", "invalidate_permissions"]


@pytest.mark.asyncio
async def test_purge_raises_when_a_soft_deleted_account_was_reactivated_before_the_lock(mocker):
    """Regression guard: a batch job (account_purge_tasks.py) can hold a
    stale `user` snapshot (deleted_at set) read well before this call. If
    the row-lock re-read shows deleted_at is now None, a reactivation raced
    the purge and it must be refused, not silently proceed on the stale
    snapshot."""
    mocker.patch(
        f"{MODULE}.user_crud.lock_by_id",
        new_callable=AsyncMock,
        return_value=_FakeUser("reactivated-before-purge@example.com", deleted_at=None),
    )
    revoke_mock = mocker.patch(
        f"{MODULE}.refresh_token_service.revoke_all_tokens_for_user", new_callable=AsyncMock, return_value=2
    )
    delete_mock = mocker.patch(f"{MODULE}.user_crud.delete", new_callable=AsyncMock)
    stale_user = _FakeUser("reactivated-before-purge@example.com")  # deleted_at set, per the default

    with pytest.raises(AccountNoLongerEligibleForPurgeError):
        await purge_user_account(stale_user, db=MagicMock(), purged_by="system:grace_period_purge")

    revoke_mock.assert_not_awaited()
    delete_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_purge_raises_when_the_row_no_longer_exists(mocker):
    mocker.patch(f"{MODULE}.user_crud.lock_by_id", new_callable=AsyncMock, return_value=None)
    delete_mock = mocker.patch(f"{MODULE}.user_crud.delete", new_callable=AsyncMock)
    user = _FakeUser("already-gone@example.com")

    with pytest.raises(AccountNoLongerEligibleForPurgeError):
        await purge_user_account(user, db=MagicMock(), purged_by="admin@example.com")

    delete_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_purge_proceeds_for_a_still_active_account_an_admin_purges_directly(mocker):
    """An admin purging a never-soft-deleted account (DELETE /users/{email}/purge
    with no prior soft delete) is a legitimate, separate call shape with no
    deleted_at precondition to regress on -- must not be rejected by the
    reactivation-race guard above."""
    mocker.patch(
        f"{MODULE}.user_crud.lock_by_id",
        new_callable=AsyncMock,
        return_value=_FakeUser("still-active@example.com", deleted_at=None),
    )
    delete_mock = mocker.patch(f"{MODULE}.user_crud.delete", new_callable=AsyncMock)
    user = _FakeUser("still-active@example.com", deleted_at=None)

    await purge_user_account(user, db=MagicMock(), purged_by="admin@example.com")

    delete_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_purge_passes_the_users_id_to_the_row_lock(mocker):
    lock_mock = mocker.patch(
        f"{MODULE}.user_crud.lock_by_id",
        new_callable=AsyncMock,
        return_value=_FakeUser("purge-me@example.com", id=42),
    )
    user = _FakeUser("purge-me@example.com", id=42)
    db = MagicMock()

    await purge_user_account(user, db=db, purged_by="admin@example.com")

    lock_mock.assert_awaited_once_with(42, db)


@pytest.mark.asyncio
async def test_purge_returns_the_revoked_session_count_unchanged(mocker):
    """The cache-invalidation addition must not alter this function's
    existing return contract (account_purge_tasks.py's own caller doesn't
    use it, but the admin purge route reports it in its response)."""
    mocker.patch(f"{MODULE}.authorization_cache_service.invalidate_user_policies", new_callable=AsyncMock)
    mocker.patch(f"{MODULE}.authorization_cache_service.invalidate_user_permissions", new_callable=AsyncMock)
    user = _FakeUser("count-check@example.com")

    result = await purge_user_account(user, db=MagicMock(), purged_by="admin@example.com")

    assert result == 2


@pytest.mark.asyncio
async def test_purge_anonymizes_the_purged_users_own_audit_log_rows(mocker):
    """Without this, a hard-purged account's email/IP/user-agent
    stayed readable forever in security_audit_log/authorization_audit_log
    (no FK, append-only, no retention job) - "deleted" meant only the
    `users` row. Both audit tables must be anonymized for this exact
    email, after the row delete (ON DELETE CASCADE already removed
    Manage Sessions rows by then, same ordering reasoning as the existing
    revoke-before-delete comment)."""
    security_mock = mocker.patch(f"{MODULE}.audit_log_repository.anonymize_for_user", new_callable=AsyncMock, return_value=3)
    authz_mock = mocker.patch(
        f"{MODULE}.authorization_audit_log_repository.anonymize_for_user", new_callable=AsyncMock, return_value=5
    )
    user = _FakeUser("purge-me@example.com")

    await purge_user_account(user, db=MagicMock(), purged_by="admin@example.com")

    security_mock.assert_awaited_once_with("purge-me@example.com", mocker.ANY)
    authz_mock.assert_awaited_once_with("purge-me@example.com", mocker.ANY)


@pytest.mark.asyncio
async def test_purge_anonymizes_history_before_writing_its_own_account_purged_entry(mocker):
    """Regression: audit_log_repository.anonymize_for_user matches every row
    with this user_email, with no exception for rows written moments
    earlier in the same call. If the ACCOUNT_PURGED entry were written
    first and anonymized second, the one audit row specifically meant to
    make this purge reviewable would immediately have its own email nulled
    out by the sweep that follows it, self-erasing the exact fact ("which
    account was purged") the log entry exists to record. The anonymize
    calls must happen before log_security_event, not after, so the
    ACCOUNT_PURGED row is written after the sweep and survives intact."""
    call_order = []
    mocker.patch(
        f"{MODULE}.audit_log_repository.anonymize_for_user",
        new_callable=AsyncMock,
        side_effect=lambda *args: (call_order.append("anonymize_security"), 0)[1],
    )
    mocker.patch(
        f"{MODULE}.authorization_audit_log_repository.anonymize_for_user",
        new_callable=AsyncMock,
        side_effect=lambda *args: (call_order.append("anonymize_authz"), 0)[1],
    )
    mocker.patch(
        f"{MODULE}.log_security_event",
        new_callable=AsyncMock,
        side_effect=lambda *args, **kwargs: call_order.append("log_account_purged"),
    )
    user = _FakeUser("purge-me@example.com")

    await purge_user_account(user, db=MagicMock(), purged_by="admin@example.com")

    assert call_order.index("anonymize_security") < call_order.index("log_account_purged")
    assert call_order.index("anonymize_authz") < call_order.index("log_account_purged")
