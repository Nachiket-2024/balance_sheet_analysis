# tests/backend/mystic_auth/unit/auth/token_logic/test_jwt_service_jti_revocation_unit.py
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from backend.mystic_auth.auth.token_logic.jwt_service import jwt_service

MODULE = "backend.mystic_auth.auth.token_logic.jwt_service"


# ---------------------------- is_token_revoked_by_jti ----------------------------
# Backs claim_jti_for_rotation's single-use guarantee: verify_token checks
# this for every token, but in practice only refresh-token jtis ever get
# an entry here (via claim_jti_for_rotation); access tokens are governed
# purely by version, not by jti.

@pytest.mark.asyncio
async def test_is_token_revoked_by_jti_checks_valkey_key(mocker):
    exists_mock = mocker.patch(f"{MODULE}.valkey_client.exists", new_callable=AsyncMock, return_value=1)

    assert await jwt_service.is_token_revoked_by_jti("some-jti") is True
    exists_mock.assert_awaited_once_with("revoked:some-jti")


@pytest.mark.asyncio
async def test_is_token_revoked_by_jti_missing_jti_is_not_revoked():
    # Tokens with no jti (e.g. password reset tokens) were never eligible for
    # this check.
    assert await jwt_service.is_token_revoked_by_jti(None) is False


# ---------------------------- claim_jti_for_rotation (durable unique claim) ----------------------------

@asynccontextmanager
async def _fake_db_session(mocker, rows):
    pending = list(rows)
    result = SimpleNamespace(first=lambda: pending.pop(0))
    session = SimpleNamespace(execute=AsyncMock(return_value=result), commit=AsyncMock())
    @asynccontextmanager
    async def context():
        yield session
    mocker.patch(f"{MODULE}.database.async_session", side_effect=context)
    yield session


@pytest.mark.asyncio
async def test_claim_jti_for_rotation_uses_durable_database_claim(mocker):
    mocker.patch(f"{MODULE}.valkey_client.exists", new_callable=AsyncMock, return_value=0)
    consumed_at = datetime.now(UTC)
    async with _fake_db_session(mocker, [(consumed_at, "10.0.0.1", 2, 3)]) as session:
        claim = await jwt_service.claim_jti_for_rotation(
            "jti-1", 9999999999, "user@example.com", "10.0.0.1", 2, 3
        )

    assert claim.claimed is True
    assert claim.consumed_at == consumed_at
    assert (claim.account_ver, claim.chain_ver) == (2, 3)
    sql = str(session.execute.call_args.args[0])
    assert "INSERT INTO consumed_refresh_tokens" in sql
    assert "ON CONFLICT (jti) DO NOTHING" in sql
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_claim_jti_for_rotation_returns_original_claim_when_already_claimed(mocker):
    mocker.patch(f"{MODULE}.valkey_client.exists", new_callable=AsyncMock, return_value=0)
    consumed_at = datetime.now(UTC)
    async with _fake_db_session(mocker, [None, (consumed_at, "10.0.0.1", 2, 3)]):
        claim = await jwt_service.claim_jti_for_rotation(
            "jti-1", 9999999999, "user@example.com", "10.0.0.1", 9, 9
        )
    assert claim.claimed is False
    assert claim.consumed_at == consumed_at
    assert (claim.account_ver, claim.chain_ver) == (2, 3)


@pytest.mark.asyncio
async def test_claim_jti_for_rotation_honors_legacy_valkey_marker(mocker):
    legacy = mocker.patch(f"{MODULE}.valkey_client.exists", new_callable=AsyncMock, return_value=1)
    db = mocker.patch(f"{MODULE}.database.async_session")
    claim = await jwt_service.claim_jti_for_rotation("jti-1", 9999999999)
    assert claim.claimed is False
    assert claim.legacy_valkey_marker is True
    legacy.assert_awaited_once_with("revoked:jti-1")
    db.assert_not_called()


@pytest.mark.asyncio
async def test_claim_jti_for_rotation_requires_expiry(mocker):
    mocker.patch(f"{MODULE}.valkey_client.exists", new_callable=AsyncMock, return_value=0)
    with pytest.raises(Exception, match="durable refresh rotation store unavailable"):
        await jwt_service.claim_jti_for_rotation("jti-1", exp=None)


# ---------------------------- End-to-end: verify_token honors the single-use claim ----------------------------

@pytest.mark.asyncio
async def test_verify_token_rejects_when_jti_is_already_claimed(mocker):
    mocker.patch(f"{MODULE}.valkey_client.get", new_callable=AsyncMock, return_value=None)
    token = await jwt_service.create_refresh_token(email="user@example.com", chain_id="chain-1")

    import jwt as pyjwt

    from backend.mystic_auth.core.settings import settings
    payload = pyjwt.decode(
        token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM], options={"verify_aud": False}
    )

    # Simulate only this jti being claimed in Valkey
    async def fake_exists(key):
        return 1 if key == f"revoked:{payload['jti']}" else 0

    mocker.patch(f"{MODULE}.valkey_client.exists", side_effect=fake_exists)

    assert await jwt_service.verify_token(token, expected_type="refresh") is None


# ---------------------------- refresh_token_service.revoke_all_tokens_for_user ----------------------------
# The whole-account revoke: one Valkey INCR
# (jwt_service.bump_account_version), no per-token iteration. Replaces
# the old per-jti-registry loop entirely.

@pytest.mark.asyncio
async def test_revoke_all_tokens_for_user_bumps_the_account_version(mocker):
    from backend.mystic_auth.auth.refresh_token_logic.refresh_token_service import (
        refresh_token_service,
    )

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
        "backend.mystic_auth.user_session.session_events.valkey_client.publish", new_callable=AsyncMock
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
    method) there's nothing to count from, so the returned count is just
    0. The actual revoke (the version bump) still happens regardless."""
    from backend.mystic_auth.auth.refresh_token_logic.refresh_token_service import (
        refresh_token_service,
    )

    bump_mock = mocker.patch(
        "backend.mystic_auth.auth.refresh_token_logic.refresh_token_service.jwt_service.bump_account_version",
        new_callable=AsyncMock,
    )
    mocker.patch(
        "backend.mystic_auth.auth.refresh_token_logic.refresh_token_service.session_service.revoke_all_sessions",
        new_callable=AsyncMock,
    )
    mocker.patch("backend.mystic_auth.user_session.session_events.valkey_client.publish", new_callable=AsyncMock)

    revoked_count = await refresh_token_service.revoke_all_tokens_for_user("user@example.com", db=None)

    assert revoked_count == 0
    bump_mock.assert_awaited_once()


# ---------------------------- refresh_token_service.revoke_chain_for_user ----------------------------
# The single-session revoke: one Valkey INCR scoped to a chain_id, never
# touching any other session on the account.

@pytest.mark.asyncio
async def test_revoke_chain_for_user_bumps_only_that_chain(mocker):
    from backend.mystic_auth.auth.refresh_token_logic.refresh_token_service import (
        refresh_token_service,
    )

    bump_mock = mocker.patch(
        "backend.mystic_auth.auth.refresh_token_logic.refresh_token_service.jwt_service.bump_chain_version",
        new_callable=AsyncMock,
    )
    revoke_chain_mock = mocker.patch(
        "backend.mystic_auth.auth.refresh_token_logic.refresh_token_service.session_service.revoke_chain",
        new_callable=AsyncMock,
    )
    publish_mock = mocker.patch(
        "backend.mystic_auth.user_session.session_events.valkey_client.publish", new_callable=AsyncMock
    )

    await refresh_token_service.revoke_chain_for_user("user@example.com", "chain-A", db=None)

    bump_mock.assert_awaited_once_with("user@example.com", "chain-A")
    revoke_chain_mock.assert_awaited_once_with(None, "chain-A")
    publish_mock.assert_awaited_once_with("session_events:user@example.com", mocker.ANY)


# ---------------------------- is_benign_duplicate_rotation (database window) ----------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("age", "stored_ip", "request_ip", "expected"),
    [
        (2, "10.0.0.1", "10.0.0.1", True),
        (11, "10.0.0.1", "10.0.0.1", False),
        (1, "10.0.0.1", "198.51.100.7", False),
    ],
)
async def test_benign_duplicate_uses_database_consumption_record(mocker, age, stored_ip, request_ip, expected):
    mocker.patch(f"{MODULE}.settings.REFRESH_TOKEN_REUSE_GRACE_SECONDS", 10)
    consumed_at = datetime.now(UTC) - timedelta(seconds=age)
    result = SimpleNamespace(first=lambda: (consumed_at, stored_ip))
    session = SimpleNamespace(execute=AsyncMock(return_value=result))
    @asynccontextmanager
    async def context():
        yield session
    mocker.patch(f"{MODULE}.database.async_session", side_effect=context)

    assert await jwt_service.is_benign_duplicate_rotation("jti-1", request_ip) is expected


@pytest.mark.asyncio
async def test_benign_duplicate_false_when_grace_disabled(mocker):
    mocker.patch(f"{MODULE}.settings.REFRESH_TOKEN_REUSE_GRACE_SECONDS", 0)
    db = mocker.patch(f"{MODULE}.database.async_session")
    assert await jwt_service.is_benign_duplicate_rotation("jti-1", "10.0.0.1") is False
    db.assert_not_called()
