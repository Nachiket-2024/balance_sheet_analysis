# tests/backend/mystic_auth/unit/test_refresh_token_unit.py
from unittest.mock import AsyncMock

import pytest
from backend.mystic_auth.auth.refresh_token_logic.refresh_token_service import (
    refresh_token_service,
)

MODULE = "backend.mystic_auth.auth.refresh_token_logic.refresh_token_service.jwt_service"


@pytest.mark.asyncio
async def test_refresh_tokens_rotates_on_valid_unused_token(mocker):
    decode_mock = mocker.patch(
        f"{MODULE}.decode_payload",
        new_callable=AsyncMock,
        return_value={
            "email": "user@example.com", "role": "user", "type": "refresh",
            "jti": "jti-1", "chain": "chain-1", "exp": 123,
        },
    )
    claim_mock = mocker.patch(f"{MODULE}.claim_jti_for_rotation", new_callable=AsyncMock, return_value=True)
    mocker.patch(f"{MODULE}.create_access_token", new_callable=AsyncMock, return_value="new-access")
    mocker.patch(f"{MODULE}.create_refresh_token", new_callable=AsyncMock, return_value="new-refresh")

    result = await refresh_token_service.refresh_tokens("old-refresh-token")

    assert result == {"access_token": "new-access", "refresh_token": "new-refresh"}
    # The presented (old) token must be decoded exactly once to check
    # revocation/type, not re-decoded separately for that same purpose. A
    # second decode of the newly-minted refresh token is expected here too
    # (session_service.py's rotation tracking for the Manage Sessions card
    # needs the new token's jti) - a different token, a different purpose,
    # not the redundant re-decode this guard originally protected against.
    assert decode_mock.await_count == 2
    decode_mock.assert_any_await("old-refresh-token")
    claim_mock.assert_awaited_once_with("jti-1", 123, "user@example.com")


@pytest.mark.asyncio
async def test_refresh_tokens_rejects_undecodable_token(mocker):
    mocker.patch(f"{MODULE}.decode_payload", new_callable=AsyncMock, return_value=None)
    claim_mock = mocker.patch(f"{MODULE}.claim_jti_for_rotation", new_callable=AsyncMock)

    result = await refresh_token_service.refresh_tokens("bad-token")

    assert result is None
    # An expired/malformed token never decodes, so there's no jti to even
    # attempt claiming.
    claim_mock.assert_not_called()


@pytest.mark.asyncio
async def test_refresh_tokens_rotates_for_account_with_no_role_claim(mocker):
    # decode_payload's returned claims carry no "role" key at all (the JWT
    # role claim was removed entirely); rotation must not depend on it.
    decode_mock = mocker.patch(
        f"{MODULE}.decode_payload",
        new_callable=AsyncMock,
        return_value={
            "email": "oauth-user@example.com", "type": "refresh",
            "jti": "jti-2", "chain": "chain-2", "exp": 456,
        },
    )
    mocker.patch(f"{MODULE}.claim_jti_for_rotation", new_callable=AsyncMock, return_value=True)
    create_access_mock = mocker.patch(f"{MODULE}.create_access_token", new_callable=AsyncMock, return_value="new-access")
    create_refresh_mock = mocker.patch(f"{MODULE}.create_refresh_token", new_callable=AsyncMock, return_value="new-refresh")

    result = await refresh_token_service.refresh_tokens("roleless-refresh-token")

    assert result == {"access_token": "new-access", "refresh_token": "new-refresh"}
    # See test_refresh_tokens_rotates_on_valid_unused_token's identical
    # comment: a second decode of the newly-minted token is expected here
    # too, for Manage Sessions rotation tracking.
    assert decode_mock.await_count == 2
    decode_mock.assert_any_await("roleless-refresh-token")
    # chain_id explicitly carried forward from the rotated-away token's own
    # "chain" claim, both for the new access token (previously never chain-
    # aware) and the new refresh token.
    create_access_mock.assert_awaited_once_with("oauth-user@example.com", "chain-2")
    create_refresh_mock.assert_awaited_once_with("oauth-user@example.com", "chain-2")


@pytest.mark.asyncio
async def test_refresh_tokens_rejects_a_token_with_no_chain_claim(mocker):
    """A legacy token minted before chain tracking shipped carries no
    "chain" claim - rotation requires one (every access token must be
    chain-aware to support a targeted revoke), so this is rejected rather
    than silently minting an orphan chain. Forces one clean re-login,
    an acceptable one-time cost for a pre-upgrade session."""
    mocker.patch(
        f"{MODULE}.decode_payload",
        new_callable=AsyncMock,
        return_value={"email": "user@example.com", "type": "refresh", "jti": "jti-legacy", "exp": 123},
    )
    mocker.patch(f"{MODULE}.claim_jti_for_rotation", new_callable=AsyncMock, return_value=True)
    create_access_mock = mocker.patch(f"{MODULE}.create_access_token", new_callable=AsyncMock)

    result = await refresh_token_service.refresh_tokens("legacy-refresh-token")

    assert result is None
    create_access_mock.assert_not_called()


@pytest.mark.asyncio
async def test_refresh_tokens_rejects_wrong_type_token_without_treating_it_as_reuse(mocker):
    mocker.patch(
        f"{MODULE}.decode_payload",
        new_callable=AsyncMock,
        return_value={"email": "user@example.com", "role": "user", "type": "access", "jti": "jti-1", "exp": 123},
    )
    claim_mock = mocker.patch(f"{MODULE}.claim_jti_for_rotation", new_callable=AsyncMock)
    revoke_all_mock = mocker.patch(
        "backend.mystic_auth.auth.refresh_token_logic.refresh_token_service.RefreshTokenService.revoke_all_tokens_for_user",
        new_callable=AsyncMock,
    )

    result = await refresh_token_service.refresh_tokens("access-token-used-as-refresh")

    assert result is None
    # A wrong-type token must be rejected before ever being claimed/revoked;
    # it should never be burned as if it were a genuine refresh token.
    claim_mock.assert_not_called()
    # And, not being revoked, it's just rejected, not treated as reuse: no
    # session-wide revocation should be triggered.
    revoke_all_mock.assert_not_called()


@pytest.mark.asyncio
async def test_refresh_tokens_reuse_of_a_pre_chain_token_falls_back_to_revoking_everything(mocker):
    """A reused token with no "chain" claim (minted before chain tracking
    shipped) has unknown lineage, so there's nothing to scope a targeted
    revoke to - this is the maximally-safe fallback, same behavior as
    before chain tracking existed."""
    decode_mock = mocker.patch(
        f"{MODULE}.decode_payload",
        new_callable=AsyncMock,
        return_value={"email": "victim@example.com", "type": "refresh", "jti": "stolen-jti"},
    )
    mocker.patch(f"{MODULE}.claim_jti_for_rotation", new_callable=AsyncMock, return_value=False)
    revoke_all_mock = mocker.patch(
        "backend.mystic_auth.auth.refresh_token_logic.refresh_token_service.RefreshTokenService.revoke_all_tokens_for_user",
        new_callable=AsyncMock,
        return_value=3,
    )
    create_access_mock = mocker.patch(f"{MODULE}.create_access_token", new_callable=AsyncMock)

    result = await refresh_token_service.refresh_tokens("stolen-and-replayed-token")

    assert result is None
    decode_mock.assert_awaited_once_with("stolen-and-replayed-token")
    revoke_all_mock.assert_awaited_once_with("victim@example.com", None)
    # A reused token must never proceed to rotation once the claim fails.
    create_access_mock.assert_not_called()


@pytest.mark.asyncio
async def test_refresh_tokens_reuse_with_a_chain_scopes_revocation_to_that_chain_only(mocker):
    """Regression guard: reusing a token from chain A must revoke only
    chain A, never every session on the account - a genuinely unrelated
    session (e.g. a fresh login that happened after this token was already
    revoked by an intentional logout-all elsewhere) must survive. Before
    this, _handle_reuse_detected always called revoke_all_tokens_for_user,
    which had no concept of "unrelated" and killed everything."""
    decode_mock = mocker.patch(
        f"{MODULE}.decode_payload",
        new_callable=AsyncMock,
        return_value={"email": "victim@example.com", "type": "refresh", "jti": "stale-jti", "chain": "chain-A"},
    )
    mocker.patch(f"{MODULE}.claim_jti_for_rotation", new_callable=AsyncMock, return_value=False)
    revoke_chain_mock = mocker.patch(
        "backend.mystic_auth.auth.refresh_token_logic.refresh_token_service.RefreshTokenService.revoke_chain_for_user",
        new_callable=AsyncMock,
    )
    revoke_all_mock = mocker.patch(
        "backend.mystic_auth.auth.refresh_token_logic.refresh_token_service.RefreshTokenService.revoke_all_tokens_for_user",
        new_callable=AsyncMock,
    )
    create_access_mock = mocker.patch(f"{MODULE}.create_access_token", new_callable=AsyncMock)

    result = await refresh_token_service.refresh_tokens("stale-and-replayed-token")

    assert result is None
    decode_mock.assert_awaited_once_with("stale-and-replayed-token")
    revoke_chain_mock.assert_awaited_once_with("victim@example.com", "chain-A", None)
    # The account-wide, everything-goes fallback must never run when the
    # chain is known.
    revoke_all_mock.assert_not_called()
    create_access_mock.assert_not_called()


@pytest.mark.asyncio
async def test_refresh_tokens_reuse_with_missing_email_does_not_crash(mocker):
    mocker.patch(
        f"{MODULE}.decode_payload",
        new_callable=AsyncMock,
        return_value={"type": "refresh", "jti": "stolen-jti"},
    )
    # The claim is attempted (and fails) before email is required, so a
    # reused token missing the email claim still reaches reuse handling,
    # which itself copes with a missing email gracefully.
    mocker.patch(f"{MODULE}.claim_jti_for_rotation", new_callable=AsyncMock, return_value=False)
    revoke_all_mock = mocker.patch(
        "backend.mystic_auth.auth.refresh_token_logic.refresh_token_service.RefreshTokenService.revoke_all_tokens_for_user",
        new_callable=AsyncMock,
    )

    result = await refresh_token_service.refresh_tokens("garbage-payload-token")

    assert result is None
    revoke_all_mock.assert_not_called()


@pytest.mark.asyncio
async def test_refresh_tokens_rejects_valid_type_token_missing_email_after_successful_claim(mocker):
    # A payload that claims successfully (jti wasn't already revoked) but
    # carries no email claim at all must still be rejected: email is
    # required to mint new tokens.
    mocker.patch(
        f"{MODULE}.decode_payload",
        new_callable=AsyncMock,
        return_value={"type": "refresh", "jti": "jti-3", "chain": "chain-3", "exp": 999},
    )
    mocker.patch(f"{MODULE}.claim_jti_for_rotation", new_callable=AsyncMock, return_value=True)
    create_access_mock = mocker.patch(f"{MODULE}.create_access_token", new_callable=AsyncMock)

    result = await refresh_token_service.refresh_tokens("no-email-token")

    assert result is None
    create_access_mock.assert_not_called()


@pytest.mark.asyncio
async def test_decode_payload_ignores_revocation_status(mocker):
    from backend.mystic_auth.auth.token_logic.jwt_service import jwt_service

    mocker.patch(
        "backend.mystic_auth.auth.token_logic.jwt_service.redis_client.get",
        new_callable=AsyncMock,
        return_value=None,
    )
    token = await jwt_service.create_refresh_token(email="user@example.com", chain_id="chain-1")

    # decode_payload must return the claims even though revoke status is never
    # consulted : it's used precisely for tokens Redis already marks as revoked
    payload = await jwt_service.decode_payload(token)

    assert payload["email"] == "user@example.com"
    assert payload["type"] == "refresh"


@pytest.mark.asyncio
async def test_decode_payload_returns_none_for_garbage_token():
    from backend.mystic_auth.auth.token_logic.jwt_service import jwt_service

    assert await jwt_service.decode_payload("not-a-real-jwt") is None
