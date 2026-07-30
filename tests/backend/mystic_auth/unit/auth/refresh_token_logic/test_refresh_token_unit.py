# tests/backend/mystic_auth/unit/test_refresh_token_unit.py
from unittest.mock import AsyncMock

import pytest
from backend.mystic_auth.auth.refresh_token_logic.refresh_token_service import refresh_token_service

MODULE = "backend.mystic_auth.auth.refresh_token_logic.refresh_token_service.jwt_service"


@pytest.mark.asyncio
async def test_refresh_tokens_rotates_on_valid_unused_token(mocker):
    decode_mock = mocker.patch(
        f"{MODULE}.decode_payload",
        new_callable=AsyncMock,
        return_value={"email": "user@example.com", "role": "user", "type": "refresh", "jti": "jti-1", "exp": 123},
    )
    claim_mock = mocker.patch(f"{MODULE}.claim_jti_for_rotation", new_callable=AsyncMock, return_value=True)
    mocker.patch(f"{MODULE}.create_access_token", new_callable=AsyncMock, return_value="new-access")
    mocker.patch(f"{MODULE}.create_refresh_token", new_callable=AsyncMock, return_value="new-refresh")

    result = await refresh_token_service.refresh_tokens("old-refresh-token")

    assert result == {"access_token": "new-access", "refresh_token": "new-refresh"}
    # The token must be decoded exactly once for the whole rotation, not
    # re-decoded separately to check revocation/type and again to revoke it.
    decode_mock.assert_awaited_once_with("old-refresh-token")
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
        return_value={"email": "oauth-user@example.com", "type": "refresh", "jti": "jti-2", "exp": 456},
    )
    mocker.patch(f"{MODULE}.claim_jti_for_rotation", new_callable=AsyncMock, return_value=True)
    create_access_mock = mocker.patch(f"{MODULE}.create_access_token", new_callable=AsyncMock, return_value="new-access")
    create_refresh_mock = mocker.patch(f"{MODULE}.create_refresh_token", new_callable=AsyncMock, return_value="new-refresh")

    result = await refresh_token_service.refresh_tokens("roleless-refresh-token")

    assert result == {"access_token": "new-access", "refresh_token": "new-refresh"}
    decode_mock.assert_awaited_once_with("roleless-refresh-token")
    create_access_mock.assert_awaited_once_with("oauth-user@example.com")
    create_refresh_mock.assert_awaited_once_with("oauth-user@example.com")


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
async def test_refresh_tokens_reuse_of_revoked_token_revokes_all_sessions(mocker):
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
    revoke_all_mock.assert_awaited_once_with("victim@example.com")
    # A reused token must never proceed to rotation once the claim fails.
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
        return_value={"type": "refresh", "jti": "jti-3", "exp": 999},
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
        "backend.mystic_auth.auth.token_logic.jwt_service.redis_client.hset",
        new_callable=AsyncMock,
    )
    token = await jwt_service.create_refresh_token(email="user@example.com")

    # decode_payload must return the claims even though revoke status is never
    # consulted : it's used precisely for tokens Redis already marks as revoked
    payload = await jwt_service.decode_payload(token)

    assert payload["email"] == "user@example.com"
    assert payload["type"] == "refresh"


@pytest.mark.asyncio
async def test_decode_payload_returns_none_for_garbage_token():
    from backend.mystic_auth.auth.token_logic.jwt_service import jwt_service

    assert await jwt_service.decode_payload("not-a-real-jwt") is None
