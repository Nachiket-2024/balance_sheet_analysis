# tests/backend/mystic_auth/unit/test_jti_revocation_unit.py
from unittest.mock import AsyncMock

import pytest
from backend.mystic_auth.auth.token_logic.jwt_service import jwt_service

MODULE = "backend.mystic_auth.auth.token_logic.jwt_service"


# ---------------------------- is_token_revoked_by_jti ----------------------------
# Backs claim_jti_for_rotation's single-use guarantee: verify_token checks
# this for every token, but in practice only refresh-token jtis ever get an
# entry here now (via claim_jti_for_rotation) - access tokens are governed
# purely by version, not by jti.

@pytest.mark.asyncio
async def test_is_token_revoked_by_jti_checks_redis_key(mocker):
    exists_mock = mocker.patch(f"{MODULE}.redis_client.exists", new_callable=AsyncMock, return_value=1)

    assert await jwt_service.is_token_revoked_by_jti("some-jti") is True
    exists_mock.assert_awaited_once_with("revoked:some-jti")


@pytest.mark.asyncio
async def test_is_token_revoked_by_jti_missing_jti_is_not_revoked():
    # Tokens with no jti (e.g. password reset tokens) were never eligible for
    # this check.
    assert await jwt_service.is_token_revoked_by_jti(None) is False


# ---------------------------- claim_jti_for_rotation (atomic check-and-claim) ----------------------------
#
# Regression guard for the refresh-token concurrent double-spend race: two
# requests presenting the same still-valid refresh token must not both be
# able to rotate it. claim_jti_for_rotation uses a single atomic Redis
# SET...NX so only one caller can ever win the claim for a given jti. This
# is a narrower problem than "is this session still authorized" (the
# account_ver/chain_ver checks in verify_token) and not solved by it - see
# jwt_service.py's own module docstring.

@pytest.mark.asyncio
async def test_claim_jti_for_rotation_succeeds_for_an_unclaimed_jti(mocker):
    set_mock = mocker.patch(f"{MODULE}.redis_client.set", new_callable=AsyncMock, return_value=True)

    claimed = await jwt_service.claim_jti_for_rotation("jti-1", 9999999999, "user@example.com")

    assert claimed is True
    set_mock.assert_awaited_once()
    args, kwargs = set_mock.call_args
    assert args[0] == "revoked:jti-1"
    assert kwargs.get("nx") is True


@pytest.mark.asyncio
async def test_claim_jti_for_rotation_fails_for_an_already_claimed_jti(mocker):
    # Redis SET...NX returns None/False when the key already exists, this is
    # exactly what happens when two concurrent requests race on the same jti:
    # only the first SET succeeds, the second observes it already set.
    mocker.patch(f"{MODULE}.redis_client.set", new_callable=AsyncMock, return_value=None)

    claimed = await jwt_service.claim_jti_for_rotation("jti-1", 9999999999, "user@example.com")

    assert claimed is False


@pytest.mark.asyncio
async def test_claim_jti_for_rotation_uses_minimum_ttl_of_one_for_already_expired_tokens(mocker):
    set_mock = mocker.patch(f"{MODULE}.redis_client.set", new_callable=AsyncMock, return_value=True)

    # exp far in the past would otherwise compute a negative TTL, which Redis rejects
    await jwt_service.claim_jti_for_rotation("jti-1", exp=0, email="user@example.com")

    _, kwargs = set_mock.call_args
    assert kwargs["ex"] == 1


@pytest.mark.asyncio
async def test_claim_jti_for_rotation_works_without_an_email(mocker):
    set_mock = mocker.patch(f"{MODULE}.redis_client.set", new_callable=AsyncMock, return_value=True)

    claimed = await jwt_service.claim_jti_for_rotation("jti-1", 9999999999, None)

    assert claimed is True
    set_mock.assert_awaited_once()


# ---------------------------- End-to-end: verify_token honors the single-use claim ----------------------------

@pytest.mark.asyncio
async def test_verify_token_rejects_when_jti_is_already_claimed(mocker):
    mocker.patch(f"{MODULE}.redis_client.get", new_callable=AsyncMock, return_value=None)
    token = await jwt_service.create_refresh_token(email="user@example.com", chain_id="chain-1")

    import jwt as pyjwt
    from backend.mystic_auth.core.settings import settings
    payload = pyjwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])

    # Simulate only this jti being claimed in Redis
    async def fake_exists(key):
        return 1 if key == f"revoked:{payload['jti']}" else 0

    mocker.patch(f"{MODULE}.redis_client.exists", side_effect=fake_exists)

    assert await jwt_service.verify_token(token, expected_type="refresh") is None


# ---------------------------- refresh_token_service.revoke_all_tokens_for_user ----------------------------
# The whole-account revoke: one Redis INCR (jwt_service.bump_account_version),
# no per-token iteration - see refresh_token_service.py's own docstring for
# why this replaced the old per-jti-registry loop entirely.

@pytest.mark.asyncio
async def test_revoke_all_tokens_for_user_bumps_the_account_version(mocker):
    from backend.mystic_auth.auth.refresh_token_logic.refresh_token_service import refresh_token_service

    bump_mock = mocker.patch(
        "backend.mystic_auth.auth.refresh_token_logic.refresh_token_service.jwt_service.bump_account_version",
        new_callable=AsyncMock,
    )
    mocker.patch(
        "backend.mystic_auth.auth.refresh_token_logic.refresh_token_service.session_service.count_active_sessions",
        new_callable=AsyncMock,
        return_value=2,
    )
    mocker.patch(
        "backend.mystic_auth.auth.refresh_token_logic.refresh_token_service.session_service.revoke_all_sessions",
        new_callable=AsyncMock,
    )
    publish_mock = mocker.patch(
        "backend.mystic_auth.user_session.session_events.redis_client.publish", new_callable=AsyncMock
    )

    revoked_count = await refresh_token_service.revoke_all_tokens_for_user("user@example.com", db=None)

    bump_mock.assert_awaited_once_with("user@example.com")
    # Returned purely for the caller's own audit/UX purposes (e.g. logout-
    # all's "Logged out from N devices"), from the Postgres mirror's count
    # taken right before the bump - not something the revoke itself needs.
    assert revoked_count == 2
    # Every other open tab/device on the account gets a real-time nudge to
    # re-check itself, not just wait for its next background poll.
    publish_mock.assert_awaited_once_with("session_events:user@example.com", mocker.ANY)


@pytest.mark.asyncio
async def test_revoke_all_tokens_for_user_returns_zero_without_a_db(mocker):
    """count_active_sessions needs the Postgres mirror; without `db` (a
    test-only convenience, matching every other best-effort session
    method) there's nothing to count from, so the returned count is just 0
    - the actual revoke (the version bump) still happens regardless."""
    from backend.mystic_auth.auth.refresh_token_logic.refresh_token_service import refresh_token_service

    bump_mock = mocker.patch(
        "backend.mystic_auth.auth.refresh_token_logic.refresh_token_service.jwt_service.bump_account_version",
        new_callable=AsyncMock,
    )
    mocker.patch(
        "backend.mystic_auth.auth.refresh_token_logic.refresh_token_service.session_service.revoke_all_sessions",
        new_callable=AsyncMock,
    )
    mocker.patch("backend.mystic_auth.user_session.session_events.redis_client.publish", new_callable=AsyncMock)

    revoked_count = await refresh_token_service.revoke_all_tokens_for_user("user@example.com", db=None)

    assert revoked_count == 0
    bump_mock.assert_awaited_once()


# ---------------------------- refresh_token_service.revoke_chain_for_user ----------------------------
# The single-session revoke: one Redis INCR scoped to a chain_id, never
# touching any other session on the account.

@pytest.mark.asyncio
async def test_revoke_chain_for_user_bumps_only_that_chain(mocker):
    from backend.mystic_auth.auth.refresh_token_logic.refresh_token_service import refresh_token_service

    bump_mock = mocker.patch(
        "backend.mystic_auth.auth.refresh_token_logic.refresh_token_service.jwt_service.bump_chain_version",
        new_callable=AsyncMock,
    )
    revoke_chain_mock = mocker.patch(
        "backend.mystic_auth.auth.refresh_token_logic.refresh_token_service.session_service.revoke_chain",
        new_callable=AsyncMock,
    )
    publish_mock = mocker.patch(
        "backend.mystic_auth.user_session.session_events.redis_client.publish", new_callable=AsyncMock
    )

    await refresh_token_service.revoke_chain_for_user("user@example.com", "chain-A", db=None)

    bump_mock.assert_awaited_once_with("user@example.com", "chain-A")
    revoke_chain_mock.assert_awaited_once_with(None, "chain-A")
    publish_mock.assert_awaited_once_with("session_events:user@example.com", mocker.ANY)
