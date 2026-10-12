# Durable-token-store failure coverage: bump_account_version /
# bump_chain_version returning False (Postgres unavailable) must propagate
# as TokenVersionUnavailableError instead of being swallowed into a
# false "revoked" success. Covers only the Postgres-unavailable fail-closed
# paths; see test_refresh_token_unit.py for refresh_tokens()'s
# rotation/reuse-detection coverage.
from unittest.mock import AsyncMock

import pytest

from backend.mystic_auth.auth.refresh_token_logic.refresh_token_service import (
    RefreshTokenService,
    refresh_token_service,
)
from backend.mystic_auth.auth.token_logic.jwt_service import RefreshRotationClaim
from backend.mystic_auth.auth.token_logic.token_version_store import (
    TokenVersionUnavailableError,
)

MODULE = "backend.mystic_auth.auth.refresh_token_logic.refresh_token_service.jwt_service"


@pytest.mark.asyncio
async def test_revoke_all_tokens_for_user_raises_when_account_bump_is_unconfirmed(mocker):
    mocker.patch(
        "backend.mystic_auth.auth.refresh_token_logic.refresh_token_service.session_service.count_active_sessions",
        new_callable=AsyncMock, return_value=2,
    )
    mocker.patch(f"{MODULE}.bump_account_version", new_callable=AsyncMock, return_value=False)
    revoke_sessions_mock = mocker.patch(
        "backend.mystic_auth.auth.refresh_token_logic.refresh_token_service.session_service.revoke_all_sessions",
        new_callable=AsyncMock,
    )

    with pytest.raises(TokenVersionUnavailableError):
        await RefreshTokenService.revoke_all_tokens_for_user("user@example.com")

    # The Postgres mirror must be left untouched: marking it revoked while
    # the durable token version stayed unbumped would make Manage
    # Sessions/audit logs lie about the token actually being dead.
    revoke_sessions_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_revoke_all_tokens_for_user_except_chain_raises_when_bump_is_unconfirmed(mocker):
    mocker.patch(
        "backend.mystic_auth.auth.refresh_token_logic.refresh_token_service.session_service.count_active_sessions",
        new_callable=AsyncMock, return_value=2,
    )
    mocker.patch(f"{MODULE}.bump_account_version", new_callable=AsyncMock, return_value=False)
    revoke_sessions_mock = mocker.patch(
        "backend.mystic_auth.auth.refresh_token_logic.refresh_token_service.session_service.revoke_all_sessions",
        new_callable=AsyncMock,
    )

    with pytest.raises(TokenVersionUnavailableError):
        await RefreshTokenService.revoke_all_tokens_for_user_except_chain("user@example.com", "chain-1")

    revoke_sessions_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_revoke_chain_for_user_raises_when_chain_bump_is_unconfirmed(mocker):
    mocker.patch(f"{MODULE}.bump_chain_version", new_callable=AsyncMock, return_value=False)
    revoke_chain_mock = mocker.patch(
        "backend.mystic_auth.auth.refresh_token_logic.refresh_token_service.session_service.revoke_chain",
        new_callable=AsyncMock,
    )

    with pytest.raises(TokenVersionUnavailableError):
        await RefreshTokenService.revoke_chain_for_user("user@example.com", "chain-1")

    revoke_chain_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_reuse_detection_stays_fail_closed_and_still_audits_when_bump_is_unconfirmed(mocker):
    """Even if the chain-version bump can't be confirmed (Postgres down), the
    reused token itself must still be rejected (refresh_tokens returns
    None regardless, via the "not claimed" branch), and the audit event
    must still be written, with revocation_confirmed=False so the gap is
    visible rather than indistinguishable from a real revoke."""
    decode_mock = mocker.patch(
        f"{MODULE}.decode_payload",
        new_callable=AsyncMock,
        return_value={
            "email": "victim@example.com",
            "type": "refresh",
            "jti": "stale-jti",
            "chain": "chain-A",
            "account_ver": 0,
            "chain_ver": 0,
            "exp": 1_900_000_000,
        },
    )
    mocker.patch(f"{MODULE}.is_current_version", new_callable=AsyncMock, return_value=True)
    mocker.patch(
        f"{MODULE}.claim_jti_for_rotation",
        new_callable=AsyncMock,
        return_value=RefreshRotationClaim(False, None, 0, 0, None),
    )
    mocker.patch(f"{MODULE}.is_benign_duplicate_rotation", new_callable=AsyncMock, return_value=False)
    mocker.patch(f"{MODULE}.bump_chain_version", new_callable=AsyncMock, return_value=False)
    log_event_mock = mocker.patch(
        "backend.mystic_auth.auth.refresh_token_logic.refresh_token_service.log_security_event",
        new_callable=AsyncMock,
    )
    create_access_mock = mocker.patch(f"{MODULE}.create_access_token", new_callable=AsyncMock)

    result = await refresh_token_service.refresh_tokens("stale-and-replayed-token")

    assert result is None
    decode_mock.assert_awaited_once_with("stale-and-replayed-token")
    create_access_mock.assert_not_called()

    log_event_mock.assert_awaited_once()
    _, kwargs = log_event_mock.call_args
    assert kwargs["metadata"]["revocation_confirmed"] is False
    assert kwargs["metadata"]["chain_id"] == "chain-A"
