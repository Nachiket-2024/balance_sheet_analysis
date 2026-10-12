from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from backend.mystic_auth.auth.refresh_token_logic.refresh_token_service import (
    refresh_token_service,
)
from backend.mystic_auth.auth.token_logic.jwt_service import RefreshRotationClaim

# Valkey-unavailable/fail-closed coverage (bump_account_version/
# bump_chain_version returning False) lives in
# test_refresh_token_valkey_unavailable_unit.py.
MODULE = "backend.mystic_auth.auth.refresh_token_logic.refresh_token_service.jwt_service"


def _claim(claimed: bool = True) -> RefreshRotationClaim:
    return RefreshRotationClaim(claimed, datetime.now(UTC), 0, 0, None)


@pytest.fixture(autouse=True)
def _current_versions(mocker):
    mocker.patch(f"{MODULE}.get_token_versions", new_callable=AsyncMock, return_value=(0, 0))


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
    claim_mock = mocker.patch(f"{MODULE}.claim_jti_for_rotation", new_callable=AsyncMock, return_value=_claim(True))
    mocker.patch(f"{MODULE}.create_access_token", new_callable=AsyncMock, return_value="new-access")
    mocker.patch(f"{MODULE}.create_refresh_token", new_callable=AsyncMock, return_value="new-refresh")

    result = await refresh_token_service.refresh_tokens("old-refresh-token")

    assert result == {"access_token": "new-access", "refresh_token": "new-refresh"}
    # The presented (old) token must be decoded exactly once to check
    # revocation/type, not re-decoded separately for that same purpose. A
    # second decode of the newly-minted refresh token is expected here
    # too (session_service.py's rotation tracking for the Manage Sessions
    # card needs the new token's jti): a different token, a different
    # purpose.
    assert decode_mock.await_count == 2
    decode_mock.assert_any_await("old-refresh-token")
    claim_mock.assert_awaited_once_with(
        "jti-1", 123, "user@example.com", client_ip=None, account_ver=0, chain_ver=0
    )


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
async def test_refresh_tokens_rejects_wrong_issuer_or_audience_before_claiming_jti(mocker):
    mocker.patch(
        f"{MODULE}.decode_payload",
        new_callable=AsyncMock,
        return_value={
            "email": "user@example.com",
            "type": "refresh",
            "jti": "jti-1",
            "chain": "chain-1",
            "exp": 123,
            "iss": "https://other.example.com",
        },
    )
    claim_mock = mocker.patch(f"{MODULE}.claim_jti_for_rotation", new_callable=AsyncMock)
    create_access_mock = mocker.patch(f"{MODULE}.create_access_token", new_callable=AsyncMock)

    result = await refresh_token_service.refresh_tokens("wrong-deployment-refresh-token")

    assert result is None
    claim_mock.assert_not_called()
    create_access_mock.assert_not_called()


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
    mocker.patch(f"{MODULE}.claim_jti_for_rotation", new_callable=AsyncMock, return_value=_claim(True))
    create_access_mock = mocker.patch(f"{MODULE}.create_access_token", new_callable=AsyncMock, return_value="new-access")
    create_refresh_mock = mocker.patch(f"{MODULE}.create_refresh_token", new_callable=AsyncMock, return_value="new-refresh")

    result = await refresh_token_service.refresh_tokens("roleless-refresh-token")

    assert result == {"access_token": "new-access", "refresh_token": "new-refresh"}
    # See test_refresh_tokens_rotates_on_valid_unused_token's identical
    # comment: a second decode of the newly-minted token is expected here
    # too, for Manage Sessions rotation tracking.
    assert decode_mock.await_count == 2
    decode_mock.assert_any_await("roleless-refresh-token")
    # chain_id is carried forward from the rotated-away token's own
    # "chain" claim, both for the new access token (previously never
    # chain-aware) and the new refresh token.
    create_access_mock.assert_awaited_once()
    assert create_access_mock.await_args.args == ("oauth-user@example.com", "chain-2")
    assert create_access_mock.await_args.kwargs["account_ver"] == 0
    create_refresh_mock.assert_awaited_once()
    assert create_refresh_mock.await_args.args == ("oauth-user@example.com", "chain-2")
    assert create_refresh_mock.await_args.kwargs["chain_ver"] == 0


@pytest.mark.asyncio
async def test_refresh_tokens_rejects_a_token_with_no_chain_claim(mocker):
    """A legacy token minted before chain tracking shipped carries no
    "chain" claim. Rotation requires one (every access token must be
    chain-aware to support a targeted revoke), so this is rejected
    rather than silently minting an orphan chain: an acceptable
    one-time cost of one clean re-login for a pre-upgrade session."""
    mocker.patch(
        f"{MODULE}.decode_payload",
        new_callable=AsyncMock,
        return_value={"email": "user@example.com", "type": "refresh", "jti": "jti-legacy", "exp": 123},
    )
    mocker.patch(f"{MODULE}.claim_jti_for_rotation", new_callable=AsyncMock, return_value=_claim(True))
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
async def test_refresh_tokens_reuse_with_a_chain_scopes_revocation_to_that_chain_only(mocker):
    """Regression guard: reusing a token from chain A must revoke only
    chain A, never every session on the account. A genuinely unrelated
    session (e.g. a fresh login after this token was already revoked by
    an intentional logout-all elsewhere) must survive. Before this,
    _handle_reuse_detected always called revoke_all_tokens_for_user,
    which had no concept of "unrelated" and killed everything."""
    decode_mock = mocker.patch(
        f"{MODULE}.decode_payload",
        new_callable=AsyncMock,
        return_value={"email": "victim@example.com", "type": "refresh", "jti": "stale-jti", "chain": "chain-A"},
    )
    mocker.patch(f"{MODULE}.claim_jti_for_rotation", new_callable=AsyncMock, return_value=_claim(False))
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
    mocker.patch(f"{MODULE}.claim_jti_for_rotation", new_callable=AsyncMock, return_value=_claim(False))
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
    mocker.patch(f"{MODULE}.claim_jti_for_rotation", new_callable=AsyncMock, return_value=_claim(True))
    create_access_mock = mocker.patch(f"{MODULE}.create_access_token", new_callable=AsyncMock)

    result = await refresh_token_service.refresh_tokens("no-email-token")

    assert result is None
    create_access_mock.assert_not_called()


@pytest.mark.asyncio
async def test_decode_payload_ignores_revocation_status(mocker):
    from backend.mystic_auth.auth.token_logic.jwt_service import jwt_service

    mocker.patch(
        "backend.mystic_auth.auth.token_logic.jwt_service.valkey_client.get",
        new_callable=AsyncMock,
        return_value=None,
    )
    token = await jwt_service.create_refresh_token(email="user@example.com", chain_id="chain-1")

    # decode_payload must return the claims even though revoke status is
    # never consulted: it's used precisely for tokens Valkey already marks
    # as revoked.
    payload = await jwt_service.decode_payload(token)

    assert payload["email"] == "user@example.com"
    assert payload["type"] == "refresh"


@pytest.mark.asyncio
async def test_decode_payload_returns_none_for_garbage_token():
    from backend.mystic_auth.auth.token_logic.jwt_service import jwt_service

    assert await jwt_service.decode_payload("not-a-real-jwt") is None


@pytest.mark.asyncio
async def test_refresh_tokens_duplicate_within_grace_is_rejected_without_revoking(mocker):
    mocker.patch(
        f"{MODULE}.decode_payload",
        new_callable=AsyncMock,
        return_value={
            "email": "user@example.com", "type": "refresh",
            "jti": "jti-1", "chain": "chain-1", "exp": 123,
        },
    )
    mocker.patch(f"{MODULE}.claim_jti_for_rotation", new_callable=AsyncMock, return_value=_claim(False))
    mocker.patch(f"{MODULE}.is_benign_duplicate_rotation", new_callable=AsyncMock, return_value=True)
    reuse_mock = mocker.patch.object(type(refresh_token_service), "_handle_reuse_detected", new_callable=AsyncMock)
    by_jti = mocker.patch(
        "backend.mystic_auth.auth.refresh_token_logic.refresh_token_service.session_service.rotate_session",
        new_callable=AsyncMock,
    )

    result = await refresh_token_service.refresh_tokens("dup-token", db=object())

    assert result is None
    reuse_mock.assert_not_called()
    by_jti.assert_not_awaited()


@pytest.mark.asyncio
async def test_refresh_tokens_duplicate_outside_grace_runs_reuse_detection(mocker):
    mocker.patch(
        f"{MODULE}.decode_payload",
        new_callable=AsyncMock,
        return_value={
            "email": "user@example.com", "type": "refresh",
            "jti": "jti-1", "chain": "chain-1", "exp": 123,
        },
    )
    mocker.patch(f"{MODULE}.claim_jti_for_rotation", new_callable=AsyncMock, return_value=_claim(False))
    mocker.patch(f"{MODULE}.is_benign_duplicate_rotation", new_callable=AsyncMock, return_value=False)
    create_mock = mocker.patch(f"{MODULE}.create_access_token", new_callable=AsyncMock)
    reuse_mock = mocker.patch.object(type(refresh_token_service), "_handle_reuse_detected", new_callable=AsyncMock)

    assert await refresh_token_service.refresh_tokens("stolen-token") is None

    reuse_mock.assert_awaited_once()
    create_mock.assert_not_called()
