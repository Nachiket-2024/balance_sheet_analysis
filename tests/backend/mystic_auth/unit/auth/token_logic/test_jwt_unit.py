# tests/backend/mystic_auth/unit/test_jwt_unit.py
import time
from unittest.mock import AsyncMock

import jwt as pyjwt
import pytest
from backend.mystic_auth.auth.token_logic.jwt_service import jwt_service
from backend.mystic_auth.core.settings import settings


def _decode(token: str) -> dict:
    return pyjwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])


@pytest.mark.asyncio
async def test_create_access_token_is_tagged_with_access_type(mocker):
    token = await jwt_service.create_access_token(email="user@example.com")

    payload = _decode(token)
    assert payload["type"] == "access"
    assert payload["email"] == "user@example.com"
    assert "role" not in payload


@pytest.mark.asyncio
async def test_create_refresh_token_is_tagged_with_refresh_type(mocker):
    mocker.patch(
        "backend.mystic_auth.auth.token_logic.jwt_service.redis_client.hset",
        new_callable=AsyncMock,
    )

    token = await jwt_service.create_refresh_token(email="user@example.com")

    payload = _decode(token)
    assert payload["type"] == "refresh"


@pytest.mark.asyncio
async def test_verify_token_accepts_matching_expected_type(mocker):
    mocker.patch(
        "backend.mystic_auth.auth.token_logic.jwt_service.JWTService.is_token_revoked_by_jti",
        new_callable=AsyncMock,
        return_value=False,
    )

    access_token = await jwt_service.create_access_token(email="user@example.com")

    payload = await jwt_service.verify_token(access_token, expected_type="access")

    assert payload is not None
    assert payload["email"] == "user@example.com"


@pytest.mark.asyncio
async def test_verify_token_rejects_access_token_presented_as_refresh(mocker):
    mocker.patch(
        "backend.mystic_auth.auth.token_logic.jwt_service.JWTService.is_token_revoked_by_jti",
        new_callable=AsyncMock,
        return_value=False,
    )

    access_token = await jwt_service.create_access_token(email="user@example.com")

    # An access token must never be usable at the /refresh endpoint
    assert await jwt_service.verify_token(access_token, expected_type="refresh") is None


@pytest.mark.asyncio
async def test_verify_token_rejects_refresh_token_presented_as_access(mocker):
    mocker.patch(
        "backend.mystic_auth.auth.token_logic.jwt_service.JWTService.is_token_revoked_by_jti",
        new_callable=AsyncMock,
        return_value=False,
    )
    mocker.patch(
        "backend.mystic_auth.auth.token_logic.jwt_service.redis_client.hset",
        new_callable=AsyncMock,
    )

    refresh_token = await jwt_service.create_refresh_token(email="user@example.com")

    # A refresh token must never be usable to authenticate /me or other API routes
    assert await jwt_service.verify_token(refresh_token, expected_type="access") is None


@pytest.mark.asyncio
async def test_verify_token_passes_algorithm_allowlist_as_a_list(mocker):
    # Regression guard: PyJWT's `algorithms` parameter is typed as
    # Sequence[str], which a bare string technically satisfies (strings are
    # sequences of characters), so passing settings.JWT_ALGORITHM directly
    # instead of [settings.JWT_ALGORITHM] would make PyJWT's internal
    # membership check an accidental substring match rather than an exact
    # list check. Not currently exploitable given a fixed trusted algorithm
    # setting, but the list form is the only one PyJWT's own docs endorse.
    decode_mock = mocker.patch(
        "backend.mystic_auth.auth.token_logic.jwt_service.jwt.decode",
        return_value={"jti": None, "type": "access", "email": "user@example.com"},
    )
    mocker.patch(
        "backend.mystic_auth.auth.token_logic.jwt_service.JWTService.is_token_revoked_by_jti",
        new_callable=AsyncMock,
        return_value=False,
    )

    await jwt_service.verify_token("some-token")

    _, kwargs = decode_mock.call_args
    assert kwargs["algorithms"] == [settings.JWT_ALGORITHM]
    assert isinstance(kwargs["algorithms"], list)


@pytest.mark.asyncio
async def test_decode_payload_passes_algorithm_allowlist_as_a_list(mocker):
    decode_mock = mocker.patch(
        "backend.mystic_auth.auth.token_logic.jwt_service.jwt.decode",
        return_value={"email": "user@example.com"},
    )

    await jwt_service.decode_payload("some-token")

    _, kwargs = decode_mock.call_args
    assert kwargs["algorithms"] == [settings.JWT_ALGORITHM]
    assert isinstance(kwargs["algorithms"], list)


@pytest.mark.asyncio
async def test_verify_token_rejects_a_genuinely_expired_token(mocker):
    # Real wall-clock expiry (not a mocked decode): PyJWT's own exp check
    # must reject this, and verify_token must translate that into None
    # rather than letting jwt.ExpiredSignatureError escape uncaught.
    mocker.patch(
        "backend.mystic_auth.auth.token_logic.jwt_service.JWTService.is_token_revoked_by_jti",
        new_callable=AsyncMock,
        return_value=False,
    )

    expired_token = pyjwt.encode(
        {"email": "user@example.com", "type": "access", "exp": time.time() - 60},
        settings.SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )

    assert await jwt_service.verify_token(expired_token, expected_type="access") is None


@pytest.mark.asyncio
async def test_decode_payload_rejects_a_genuinely_expired_token():
    # decode_payload is the "ignore revocation, but expiry still applies"
    # path used by refresh rotation, so it must fail the same way on a real
    # expired token, not just an undecodable/garbage one.
    expired_token = pyjwt.encode(
        {"email": "user@example.com", "type": "refresh", "exp": time.time() - 60},
        settings.SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )

    assert await jwt_service.decode_payload(expired_token) is None


@pytest.mark.asyncio
async def test_verify_token_without_expected_type_skips_type_check(mocker):
    mocker.patch(
        "backend.mystic_auth.auth.token_logic.jwt_service.JWTService.is_token_revoked_by_jti",
        new_callable=AsyncMock,
        return_value=False,
    )

    # Tokens created outside jwt_service (e.g. password reset tokens) carry no
    # "type" claim at all; verify_token must still accept them when the caller
    # doesn't ask for a specific type.
    untyped_token = pyjwt.encode(
        {"email": "user@example.com"}, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM
    )

    payload = await jwt_service.verify_token(untyped_token)

    assert payload is not None
    assert payload["email"] == "user@example.com"


# ---------------------------- Wiring: callers request the correct expected_type ----------------------------
# These confirm each caller actually asks jwt_service to enforce the right token
# type, not just that jwt_service itself is capable of enforcing it.

@pytest.mark.asyncio
async def test_current_user_handler_requires_access_type(mocker):
    from backend.mystic_auth.auth.current_user.current_user_handler import current_user_handler
    from fastapi import HTTPException

    verify_mock = mocker.patch(
        "backend.mystic_auth.auth.current_user.current_user_handler.jwt_service.verify_token",
        new_callable=AsyncMock,
        return_value=None,
    )

    with pytest.raises(HTTPException):
        await current_user_handler.get_current_user("some-token", db=None)

    verify_mock.assert_awaited_once_with("some-token", expected_type="access")


@pytest.mark.asyncio
async def test_refresh_token_service_requires_refresh_type_on_rotation(mocker):
    from backend.mystic_auth.auth.refresh_token_logic.refresh_token_service import refresh_token_service

    # refresh_tokens() decodes once via decode_payload and checks the "type"
    # claim itself (rather than delegating to verify_token) to avoid
    # decoding/checking revocation on the same token more than once.
    mocker.patch(
        "backend.mystic_auth.auth.refresh_token_logic.refresh_token_service.jwt_service.decode_payload",
        new_callable=AsyncMock,
        return_value={"email": "user@example.com", "role": "user", "type": "access", "jti": "jti-1", "exp": 1},
    )
    mocker.patch(
        "backend.mystic_auth.auth.refresh_token_logic.refresh_token_service.jwt_service.is_token_revoked_by_jti",
        new_callable=AsyncMock,
        return_value=False,
    )

    result = await refresh_token_service.refresh_tokens("some-token")

    assert result is None


@pytest.mark.asyncio
async def test_refresh_token_service_requires_refresh_type_on_revoke(mocker):
    from backend.mystic_auth.auth.refresh_token_logic.refresh_token_service import refresh_token_service

    verify_mock = mocker.patch(
        "backend.mystic_auth.auth.refresh_token_logic.refresh_token_service.jwt_service.verify_token",
        new_callable=AsyncMock,
        return_value=None,
    )

    result = await refresh_token_service.revoke_refresh_token("some-token")

    assert result is False
    verify_mock.assert_awaited_once_with("some-token", expected_type="refresh")


@pytest.mark.asyncio
async def test_create_refresh_token_prunes_already_expired_registry_entries(mocker):
    """Regression guard: a jti was previously only ever removed from the
    per-user refresh-token registry hash by an explicit revoke/rotation/
    logout-all; a token that simply went stale (never used again, just
    outlived by REFRESH_TOKEN_EXPIRE_MINUTES) left its entry there forever,
    growing the hash unboundedly over a deployment's lifetime. Minting a new
    token now sweeps already-expired entries from the same hash."""
    past = time.time() - 60
    future = time.time() + 3600
    mocker.patch(
        "backend.mystic_auth.auth.token_logic.jwt_service.redis_client.hgetall",
        new_callable=AsyncMock,
        return_value={"expired-jti-1": str(past), "expired-jti-2": str(past), "still-valid-jti": str(future)},
    )
    hset_mock = mocker.patch(
        "backend.mystic_auth.auth.token_logic.jwt_service.redis_client.hset", new_callable=AsyncMock
    )
    hdel_mock = mocker.patch(
        "backend.mystic_auth.auth.token_logic.jwt_service.redis_client.hdel", new_callable=AsyncMock
    )

    await jwt_service.create_refresh_token(email="user@example.com")

    hset_mock.assert_awaited_once()
    hdel_mock.assert_awaited_once()
    _, hdel_args = hdel_mock.call_args[0][0], set(hdel_mock.call_args[0][1:])
    assert hdel_args == {"expired-jti-1", "expired-jti-2"}


@pytest.mark.asyncio
async def test_create_refresh_token_skips_hdel_when_nothing_is_expired(mocker):
    mocker.patch(
        "backend.mystic_auth.auth.token_logic.jwt_service.redis_client.hgetall",
        new_callable=AsyncMock,
        return_value={"still-valid-jti": str(time.time() + 3600)},
    )
    mocker.patch("backend.mystic_auth.auth.token_logic.jwt_service.redis_client.hset", new_callable=AsyncMock)
    hdel_mock = mocker.patch(
        "backend.mystic_auth.auth.token_logic.jwt_service.redis_client.hdel", new_callable=AsyncMock
    )

    await jwt_service.create_refresh_token(email="user@example.com")

    hdel_mock.assert_not_called()


@pytest.mark.asyncio
async def test_create_verification_token_honors_explicit_expires_minutes():
    """Regression guard: this used to hardcode ACCESS_TOKEN_EXPIRE_MINUTES
    (15min default) regardless of the caller's requested expiry, while
    account_verification_service set the paired Redis single-use key's TTL
    (and the emailed wording) to RESET_TOKEN_EXPIRE_MINUTES (60min
    default), so the JWT itself expired 45 minutes before the email/Redis
    key said it should."""
    token = await jwt_service.create_verification_token(email="user@example.com", expires_minutes=60)

    payload = _decode(token)
    remaining = payload["exp"] - time.time()
    assert 59 * 60 < remaining <= 60 * 60


@pytest.mark.asyncio
async def test_create_verification_token_defaults_to_access_token_expiry_when_unset():
    token = await jwt_service.create_verification_token(email="user@example.com")

    payload = _decode(token)
    remaining = payload["exp"] - time.time()
    expected_seconds = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    assert expected_seconds - 60 < remaining <= expected_seconds


@pytest.mark.asyncio
async def test_account_verification_requires_verify_type(mocker):
    from backend.mystic_auth.auth.verify_account.account_verification_service import account_verification_service

    verify_mock = mocker.patch(
        "backend.mystic_auth.auth.verify_account.account_verification_service.jwt_service.verify_token",
        new_callable=AsyncMock,
        return_value=None,
    )

    result = await account_verification_service.verify_token("some-token")

    assert result is None
    verify_mock.assert_awaited_once_with("some-token", expected_type="verify")
