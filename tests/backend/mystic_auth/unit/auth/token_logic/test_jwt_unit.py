# tests/backend/mystic_auth/unit/test_jwt_unit.py
import time
from unittest.mock import AsyncMock

import jwt as pyjwt
import pytest
from backend.mystic_auth.auth.token_logic.jwt_service import jwt_service
from backend.mystic_auth.core.settings import settings

MODULE = "backend.mystic_auth.auth.token_logic.jwt_service"


def _decode(token: str) -> dict:
    return pyjwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])


def _mock_no_versions(mocker):
    """Redis GET always returns None: every version check reads as 0 (never
    revoked), the default state for a fresh account/chain."""
    mocker.patch(f"{MODULE}.redis_client.get", new_callable=AsyncMock, return_value=None)


@pytest.mark.asyncio
async def test_create_access_token_is_tagged_with_access_type(mocker):
    _mock_no_versions(mocker)

    token = await jwt_service.create_access_token(email="user@example.com", chain_id="chain-1")

    payload = _decode(token)
    assert payload["type"] == "access"
    assert payload["email"] == "user@example.com"
    assert payload["chain"] == "chain-1"
    assert "role" not in payload


@pytest.mark.asyncio
async def test_create_access_token_carries_an_iat_claim(mocker):
    _mock_no_versions(mocker)

    before = time.time()
    token = await jwt_service.create_access_token(email="user@example.com", chain_id="chain-1")
    after = time.time()

    payload = _decode(token)
    assert before - 1 <= payload["iat"] <= after + 1


@pytest.mark.asyncio
async def test_create_access_token_embeds_current_account_and_chain_versions(mocker):
    def fake_get(key):
        if key == "account_ver:user@example.com":
            return "3"
        if key == "chain_ver:user@example.com:chain-1":
            return "5"
        return None

    mocker.patch(f"{MODULE}.redis_client.get", new_callable=AsyncMock, side_effect=fake_get)

    token = await jwt_service.create_access_token(email="user@example.com", chain_id="chain-1")

    payload = _decode(token)
    assert payload["account_ver"] == 3
    assert payload["chain_ver"] == 5


@pytest.mark.asyncio
async def test_create_refresh_token_is_tagged_with_refresh_type(mocker):
    _mock_no_versions(mocker)

    token = await jwt_service.create_refresh_token(email="user@example.com", chain_id="chain-1")

    payload = _decode(token)
    assert payload["type"] == "refresh"
    assert payload["chain"] == "chain-1"


@pytest.mark.asyncio
async def test_verify_token_accepts_matching_expected_type(mocker):
    _mock_no_versions(mocker)
    mocker.patch(f"{MODULE}.JWTService.is_token_revoked_by_jti", new_callable=AsyncMock, return_value=False)

    access_token = await jwt_service.create_access_token(email="user@example.com", chain_id="chain-1")

    payload = await jwt_service.verify_token(access_token, expected_type="access")

    assert payload is not None
    assert payload["email"] == "user@example.com"


@pytest.mark.asyncio
async def test_verify_token_rejects_access_token_presented_as_refresh(mocker):
    _mock_no_versions(mocker)
    mocker.patch(f"{MODULE}.JWTService.is_token_revoked_by_jti", new_callable=AsyncMock, return_value=False)

    access_token = await jwt_service.create_access_token(email="user@example.com", chain_id="chain-1")

    # An access token must never be usable at the /refresh endpoint
    assert await jwt_service.verify_token(access_token, expected_type="refresh") is None


@pytest.mark.asyncio
async def test_verify_token_rejects_refresh_token_presented_as_access(mocker):
    _mock_no_versions(mocker)
    mocker.patch(f"{MODULE}.JWTService.is_token_revoked_by_jti", new_callable=AsyncMock, return_value=False)

    refresh_token = await jwt_service.create_refresh_token(email="user@example.com", chain_id="chain-1")

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
        f"{MODULE}.jwt.decode",
        return_value={"jti": None, "type": "access", "email": "user@example.com"},
    )
    mocker.patch(f"{MODULE}.JWTService.is_token_revoked_by_jti", new_callable=AsyncMock, return_value=False)

    await jwt_service.verify_token("some-token")

    _, kwargs = decode_mock.call_args
    assert kwargs["algorithms"] == [settings.JWT_ALGORITHM]
    assert isinstance(kwargs["algorithms"], list)


@pytest.mark.asyncio
async def test_decode_payload_passes_algorithm_allowlist_as_a_list(mocker):
    decode_mock = mocker.patch(f"{MODULE}.jwt.decode", return_value={"email": "user@example.com"})

    await jwt_service.decode_payload("some-token")

    _, kwargs = decode_mock.call_args
    assert kwargs["algorithms"] == [settings.JWT_ALGORITHM]
    assert isinstance(kwargs["algorithms"], list)


@pytest.mark.asyncio
async def test_verify_token_rejects_a_genuinely_expired_token(mocker):
    # Real wall-clock expiry (not a mocked decode): PyJWT's own exp check
    # must reject this, and verify_token must translate that into None
    # rather than letting jwt.ExpiredSignatureError escape uncaught.
    mocker.patch(f"{MODULE}.JWTService.is_token_revoked_by_jti", new_callable=AsyncMock, return_value=False)

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
    mocker.patch(f"{MODULE}.JWTService.is_token_revoked_by_jti", new_callable=AsyncMock, return_value=False)

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
    from backend.mystic_auth.auth.current_user.current_user_handler import (
        current_user_handler,
    )
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
    from backend.mystic_auth.auth.refresh_token_logic.refresh_token_service import (
        refresh_token_service,
    )

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
    from backend.mystic_auth.auth.verify_account.account_verification_service import (
        account_verification_service,
    )

    verify_mock = mocker.patch(
        "backend.mystic_auth.auth.verify_account.account_verification_service.jwt_service.verify_token",
        new_callable=AsyncMock,
        return_value=None,
    )

    result = await account_verification_service.verify_token("some-token")

    assert result is None
    verify_mock.assert_awaited_once_with("some-token", expected_type="verify")


# ---------------------------- Version-based revocation ----------------------------
# Revocation is entirely version-based now: a token is valid only if its own
# embedded account_ver and chain_ver still match Redis's current values.
# bump_account_version/bump_chain_version are what an actual revoke calls
# (see refresh_token_service.py); these tests cover the read/write/compare
# primitives in isolation.

@pytest.mark.asyncio
async def test_get_account_version_defaults_to_zero_when_never_bumped(mocker):
    mocker.patch(f"{MODULE}.redis_client.get", new_callable=AsyncMock, return_value=None)

    assert await jwt_service.get_account_version("user@example.com") == 0


@pytest.mark.asyncio
async def test_get_account_version_reads_the_stored_integer(mocker):
    mocker.patch(f"{MODULE}.redis_client.get", new_callable=AsyncMock, return_value="7")

    assert await jwt_service.get_account_version("user@example.com") == 7


@pytest.mark.asyncio
async def test_get_chain_version_defaults_to_zero_when_never_bumped(mocker):
    mocker.patch(f"{MODULE}.redis_client.get", new_callable=AsyncMock, return_value=None)

    assert await jwt_service.get_chain_version("user@example.com", "chain-1") == 0


@pytest.mark.asyncio
async def test_bump_account_version_increments_the_key(mocker):
    incr_mock = mocker.patch(f"{MODULE}.redis_client.incr", new_callable=AsyncMock)

    await jwt_service.bump_account_version("user@example.com")

    incr_mock.assert_awaited_once_with("account_ver:user@example.com")


@pytest.mark.asyncio
async def test_bump_chain_version_increments_and_sets_a_ttl(mocker):
    incr_mock = mocker.patch(f"{MODULE}.redis_client.incr", new_callable=AsyncMock)
    expire_mock = mocker.patch(f"{MODULE}.redis_client.expire", new_callable=AsyncMock)

    await jwt_service.bump_chain_version("user@example.com", "chain-1")

    incr_mock.assert_awaited_once_with("chain_ver:user@example.com:chain-1")
    # TTL'd to the refresh-token lifetime: nothing could still be validly
    # using this chain_id after that elapses anyway (see the key's own
    # module-level comment), so the key can safely expire instead of
    # accumulating one per revoked session forever.
    expire_mock.assert_awaited_once_with(
        "chain_ver:user@example.com:chain-1", settings.REFRESH_TOKEN_EXPIRE_MINUTES * 60
    )


@pytest.mark.asyncio
async def test_verify_token_rejects_a_token_whose_account_version_is_stale(mocker):
    mocker.patch(f"{MODULE}.JWTService.is_token_revoked_by_jti", new_callable=AsyncMock, return_value=False)
    # Minted with account_ver=0 (nothing bumped yet)...
    mocker.patch(f"{MODULE}.redis_client.get", new_callable=AsyncMock, return_value=None)
    token = await jwt_service.create_access_token(email="user@example.com", chain_id="chain-1")

    # ...then the account is revoked (bumped to 1) before the token is used.
    mocker.patch(f"{MODULE}.redis_client.get", new_callable=AsyncMock, return_value="1")

    assert await jwt_service.verify_token(token, expected_type="access") is None


@pytest.mark.asyncio
async def test_verify_token_accepts_a_token_minted_after_the_account_bump(mocker):
    """A token minted (e.g. by logging back in) after a revoke event must
    still work - the version is a fixed point in time, not a blanket ban on
    the account."""
    mocker.patch(f"{MODULE}.JWTService.is_token_revoked_by_jti", new_callable=AsyncMock, return_value=False)
    # Minted after the account was already bumped to version 1.
    mocker.patch(f"{MODULE}.redis_client.get", new_callable=AsyncMock, return_value="1")

    token = await jwt_service.create_access_token(email="user@example.com", chain_id="chain-1")
    payload = await jwt_service.verify_token(token, expected_type="access")

    assert payload is not None
    assert payload["email"] == "user@example.com"


@pytest.mark.asyncio
async def test_verify_token_rejects_a_token_whose_chain_version_is_stale(mocker):
    mocker.patch(f"{MODULE}.JWTService.is_token_revoked_by_jti", new_callable=AsyncMock, return_value=False)
    mocker.patch(f"{MODULE}.redis_client.get", new_callable=AsyncMock, return_value=None)
    token = await jwt_service.create_refresh_token(email="user@example.com", chain_id="chain-1")

    # Only this one chain gets revoked - a different, unrelated chain on
    # the same account would read a version of 0 and stay unaffected.
    mocker.patch(f"{MODULE}.redis_client.get", new_callable=AsyncMock, return_value="1")

    assert await jwt_service.verify_token(token, expected_type="refresh") is None


@pytest.mark.asyncio
async def test_verify_token_accepts_a_token_with_no_account_or_chain_claims(mocker):
    """A token minted before this feature shipped (or any token type that
    never carried these claims, e.g. password reset tokens) must not be
    rejected just because there's nothing to compare - same reasoning as
    the jti-less early return in is_token_revoked_by_jti."""
    mocker.patch(f"{MODULE}.JWTService.is_token_revoked_by_jti", new_callable=AsyncMock, return_value=False)

    untyped_token = pyjwt.encode(
        {"email": "user@example.com", "type": "access"}, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM
    )

    payload = await jwt_service.verify_token(untyped_token, expected_type="access")

    assert payload is not None
