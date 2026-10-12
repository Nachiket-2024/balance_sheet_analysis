# tests/backend/mystic_auth/unit/user_lifecycle/test_user_self_deletion_service_unit.py
#
# Unit coverage for finalize_self_deletion's own Valkey-failure handling.
# Regression guard for the "Valkey outage failure modes are inconsistent"
# gap: the soft-delete itself (a Postgres write) always succeeds regardless
# of whether the account-version bump can be confirmed, so a Valkey outage
# must never turn an already-successful account deletion into a raised
# exception (which would otherwise surface to the caller as a false
# failure - the account really was deleted).
from unittest.mock import AsyncMock

import pytest

from backend.mystic_auth.auth.token_logic.token_version_store import (
    TokenVersionUnavailableError,
)
from backend.mystic_auth.user_lifecycle.user_self_deletion_service import (
    finalize_self_deletion,
)

MODULE = "backend.mystic_auth.user_lifecycle.user_self_deletion_service"


class _FakeUser:
    email = "user@example.com"


@pytest.mark.asyncio
async def test_finalize_self_deletion_records_confirmed_revocation_on_success(mocker):
    mocker.patch(f"{MODULE}.user_crud.soft_delete", new_callable=AsyncMock)
    mocker.patch(f"{MODULE}.refresh_token_service.revoke_all_tokens_for_user", new_callable=AsyncMock, return_value=2)
    log_mock = mocker.patch(f"{MODULE}.log_security_event", new_callable=AsyncMock)

    revoked_count = await finalize_self_deletion(_FakeUser(), db=None)

    assert revoked_count == 2
    metadata = log_mock.await_args.kwargs["metadata"]
    assert metadata["sessions_revoked"] == 2
    assert metadata["sessions_revoked_confirmed"] is True


@pytest.mark.asyncio
async def test_finalize_self_deletion_succeeds_but_flags_unconfirmed_revocation_when_valkey_is_unreachable(mocker):
    soft_delete_mock = mocker.patch(f"{MODULE}.user_crud.soft_delete", new_callable=AsyncMock)
    mocker.patch(
        f"{MODULE}.refresh_token_service.revoke_all_tokens_for_user",
        new_callable=AsyncMock,
        side_effect=TokenVersionUnavailableError("Valkey unreachable"),
    )
    log_mock = mocker.patch(f"{MODULE}.log_security_event", new_callable=AsyncMock)

    # Must not raise: the soft-delete already happened and must be reported
    # as the success it is, not swallowed into an unhandled exception.
    revoked_count = await finalize_self_deletion(_FakeUser(), db=None)

    soft_delete_mock.assert_awaited_once()
    assert revoked_count == 0
    metadata = log_mock.await_args.kwargs["metadata"]
    assert metadata["sessions_revoked_confirmed"] is False
