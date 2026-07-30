# tests/backend/mystic_auth/unit/test_jti_revocation_unit.py
from unittest.mock import AsyncMock

import jwt as pyjwt
import pytest
from backend.mystic_auth.auth.token_logic.jwt_service import jwt_service
from backend.mystic_auth.core.settings import settings

MODULE = "backend.mystic_auth.auth.token_logic.jwt_service"


def _decode(token: str) -> dict:
    return pyjwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])


# ---------------------------- Registry keys off jti, never the raw token ----------------------------

@pytest.mark.asyncio
async def test_create_refresh_token_registers_jti_not_raw_token(mocker):
    hset_mock = mocker.patch(f"{MODULE}.redis_client.hset", new_callable=AsyncMock)

    token = await jwt_service.create_refresh_token(email="user@example.com")
    payload = _decode(token)

    hset_mock.assert_awaited_once()
    args, _ = hset_mock.call_args
    assert args[0] == "refresh_token_registry:user@example.com"
    assert args[1] == payload["jti"]
    # The raw token string must never be handed to Redis as the tracked value
    assert args[1] != token
    assert int(args[2]) == payload["exp"]


@pytest.mark.asyncio
async def test_get_all_refresh_tokens_for_user_returns_jti_registry(mocker):
    mocker.patch(
        f"{MODULE}.redis_client.hgetall",
        new_callable=AsyncMock,
        return_value={"jti-1": "1234567890"},
    )

    registry = await jwt_service.get_all_refresh_tokens_for_user("user@example.com")

    assert registry == {"jti-1": "1234567890"}


@pytest.mark.asyncio
async def test_get_all_refresh_tokens_for_user_empty(mocker):
    mocker.patch(f"{MODULE}.redis_client.hgetall", new_callable=AsyncMock, return_value={})

    assert await jwt_service.get_all_refresh_tokens_for_user("user@example.com") == {}


# ---------------------------- revoke_token / revoke_token_by_jti ----------------------------

@pytest.mark.asyncio
async def test_revoke_token_blacklists_by_jti_and_clears_registry_entry(mocker):
    set_mock = mocker.patch(f"{MODULE}.redis_client.set", new_callable=AsyncMock)
    hdel_mock = mocker.patch(f"{MODULE}.redis_client.hdel", new_callable=AsyncMock)

    token = await jwt_service.create_access_token(email="user@example.com")
    payload = _decode(token)

    result = await jwt_service.revoke_token(token, email="user@example.com")

    assert result is True
    set_mock.assert_awaited_once()
    args, kwargs = set_mock.call_args
    assert args[0] == f"revoked:{payload['jti']}"
    assert kwargs["ex"] >= 1
    # The blacklist key must be the jti, never the raw token itself
    assert token not in args[0]
    hdel_mock.assert_awaited_once_with("refresh_token_registry:user@example.com", payload["jti"])


@pytest.mark.asyncio
async def test_revoke_token_without_email_skips_registry_cleanup(mocker):
    mocker.patch(f"{MODULE}.redis_client.set", new_callable=AsyncMock)
    hdel_mock = mocker.patch(f"{MODULE}.redis_client.hdel", new_callable=AsyncMock)

    token = await jwt_service.create_access_token(email="user@example.com")
    result = await jwt_service.revoke_token(token)

    assert result is True
    hdel_mock.assert_not_called()


@pytest.mark.asyncio
async def test_revoke_token_by_jti_uses_minimum_ttl_of_one_for_already_expired_tokens(mocker):
    set_mock = mocker.patch(f"{MODULE}.redis_client.set", new_callable=AsyncMock)
    mocker.patch(f"{MODULE}.redis_client.hdel", new_callable=AsyncMock)

    # exp far in the past would otherwise compute a negative TTL, which Redis rejects
    result = await jwt_service.revoke_token_by_jti("some-jti", exp=0, email="user@example.com")

    assert result is True
    _, kwargs = set_mock.call_args
    assert kwargs["ex"] == 1


@pytest.mark.asyncio
async def test_revoke_token_without_jti_fails_gracefully(mocker):
    set_mock = mocker.patch(f"{MODULE}.redis_client.set", new_callable=AsyncMock)

    legacy_token = pyjwt.encode(
        {"email": "user@example.com", "exp": 9999999999}, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM
    )

    result = await jwt_service.revoke_token(legacy_token, email="user@example.com")

    assert result is False
    set_mock.assert_not_called()


@pytest.mark.asyncio
async def test_revoke_token_rejects_garbage_token_via_decode_payload(mocker):
    # revoke_token delegates decoding to decode_payload rather than a second,
    # separately-maintained jwt.decode call: an undecodable token must fail
    # the same way decode_payload does, not raise.
    set_mock = mocker.patch(f"{MODULE}.redis_client.set", new_callable=AsyncMock)

    result = await jwt_service.revoke_token("not-a-real-token", email="user@example.com")

    assert result is False
    set_mock.assert_not_called()


# ---------------------------- is_token_revoked / is_token_revoked_by_jti ----------------------------

@pytest.mark.asyncio
async def test_is_token_revoked_by_jti_checks_redis_key(mocker):
    exists_mock = mocker.patch(f"{MODULE}.redis_client.exists", new_callable=AsyncMock, return_value=1)

    assert await jwt_service.is_token_revoked_by_jti("some-jti") is True
    exists_mock.assert_awaited_once_with("revoked:some-jti")


@pytest.mark.asyncio
async def test_is_token_revoked_by_jti_missing_jti_is_not_revoked():
    # Tokens with no jti (e.g. password reset tokens) were never eligible for
    # this revocation mechanism, so they must not be treated as revoked.
    assert await jwt_service.is_token_revoked_by_jti(None) is False


@pytest.mark.asyncio
async def test_is_token_revoked_decodes_token_to_find_jti(mocker):
    mocker.patch(f"{MODULE}.redis_client.hset", new_callable=AsyncMock)
    exists_mock = mocker.patch(f"{MODULE}.redis_client.exists", new_callable=AsyncMock, return_value=1)

    token = await jwt_service.create_refresh_token(email="user@example.com")
    payload = _decode(token)

    assert await jwt_service.is_token_revoked(token) is True
    exists_mock.assert_awaited_once_with(f"revoked:{payload['jti']}")


@pytest.mark.asyncio
async def test_is_token_revoked_returns_false_for_garbage_token():
    assert await jwt_service.is_token_revoked("not-a-real-jwt") is False


# ---------------------------- End-to-end: verify_token honors jti revocation ----------------------------

@pytest.mark.asyncio
async def test_verify_token_rejects_when_jti_is_revoked(mocker):
    mocker.patch(f"{MODULE}.redis_client.hset", new_callable=AsyncMock)
    token = await jwt_service.create_refresh_token(email="user@example.com")
    payload = _decode(token)

    # Simulate only this jti being blacklisted in Redis
    async def fake_exists(key):
        return 1 if key == f"revoked:{payload['jti']}" else 0

    mocker.patch(f"{MODULE}.redis_client.exists", side_effect=fake_exists)

    assert await jwt_service.verify_token(token, expected_type="refresh") is None


# ---------------------------- refresh_token_service.revoke_all_tokens_for_user ----------------------------

@pytest.mark.asyncio
async def test_revoke_all_tokens_for_user_revokes_each_jti_in_registry(mocker):
    from backend.mystic_auth.auth.refresh_token_logic.refresh_token_service import refresh_token_service

    mocker.patch(
        f"{MODULE}.redis_client.hgetall",
        new_callable=AsyncMock,
        return_value={"jti-1": "1111111111", "jti-2": "2222222222"},
    )
    set_mock = mocker.patch(f"{MODULE}.redis_client.set", new_callable=AsyncMock)
    hdel_mock = mocker.patch(f"{MODULE}.redis_client.hdel", new_callable=AsyncMock)

    revoked_count = await refresh_token_service.revoke_all_tokens_for_user("user@example.com")

    assert revoked_count == 2
    assert set_mock.await_count == 2
    assert hdel_mock.await_count == 2
    hdel_mock.assert_any_call("refresh_token_registry:user@example.com", "jti-1")
    hdel_mock.assert_any_call("refresh_token_registry:user@example.com", "jti-2")


@pytest.mark.asyncio
async def test_revoke_all_tokens_for_user_empty_registry_returns_zero(mocker):
    from backend.mystic_auth.auth.refresh_token_logic.refresh_token_service import refresh_token_service

    mocker.patch(f"{MODULE}.redis_client.hgetall", new_callable=AsyncMock, return_value={})

    assert await refresh_token_service.revoke_all_tokens_for_user("user@example.com") == 0


# ---------------------------- claim_jti_for_rotation (atomic check-and-revoke) ----------------------------
#
# Regression guard for the refresh-token concurrent double-spend race: two
# requests presenting the same still-valid refresh token must not both be
# able to rotate it. claim_jti_for_rotation uses a single atomic Redis
# SET...NX so only one caller can ever win the claim for a given jti.

@pytest.mark.asyncio
async def test_claim_jti_for_rotation_succeeds_for_an_unclaimed_jti(mocker):
    set_mock = mocker.patch(f"{MODULE}.redis_client.set", new_callable=AsyncMock, return_value=True)
    hdel_mock = mocker.patch(f"{MODULE}.redis_client.hdel", new_callable=AsyncMock)

    claimed = await jwt_service.claim_jti_for_rotation("jti-1", 9999999999, "user@example.com")

    assert claimed is True
    set_mock.assert_awaited_once()
    args, kwargs = set_mock.call_args
    assert args[0] == "revoked:jti-1"
    assert kwargs.get("nx") is True
    hdel_mock.assert_awaited_once_with("refresh_token_registry:user@example.com", "jti-1")


@pytest.mark.asyncio
async def test_claim_jti_for_rotation_fails_for_an_already_claimed_jti(mocker):
    # Redis SET...NX returns None/False when the key already exists, this is
    # exactly what happens when two concurrent requests race on the same jti:
    # only the first SET succeeds, the second observes it already set.
    mocker.patch(f"{MODULE}.redis_client.set", new_callable=AsyncMock, return_value=None)
    hdel_mock = mocker.patch(f"{MODULE}.redis_client.hdel", new_callable=AsyncMock)

    claimed = await jwt_service.claim_jti_for_rotation("jti-1", 9999999999, "user@example.com")

    assert claimed is False
    # No registry cleanup for a claim that didn't win; the winning caller's
    # claim already did that.
    hdel_mock.assert_not_called()


@pytest.mark.asyncio
async def test_claim_jti_for_rotation_skips_registry_cleanup_without_email(mocker):
    mocker.patch(f"{MODULE}.redis_client.set", new_callable=AsyncMock, return_value=True)
    hdel_mock = mocker.patch(f"{MODULE}.redis_client.hdel", new_callable=AsyncMock)

    claimed = await jwt_service.claim_jti_for_rotation("jti-1", 9999999999, None)

    assert claimed is True
    hdel_mock.assert_not_called()
