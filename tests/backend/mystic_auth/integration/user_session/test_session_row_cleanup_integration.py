# tests/backend/mystic_auth/integration/user_session/test_session_row_cleanup_integration.py
#
# End-to-end coverage that user_sessions rows actually get removed, not just
# marked revoked, against the real ASGI app, real PostgreSQL, and real
# Valkey. Mirrors test_manage_sessions_integration.py's fixture/cleanup
# style. Split into its own file since these tests query user_sessions
# directly (session_repository.py/session_model.py's own contract), rather
# than only through GET /auth/sessions like the rest of that file does.
import uuid
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from backend.app.main import app
from backend.mystic_auth.auth.verify_account.account_verification_service import (
    account_verification_service,
)
from backend.mystic_auth.database.connection import database
from backend.mystic_auth.procrastinate_tasks.session_cleanup_tasks import (
    purge_expired_sessions,
)
from backend.mystic_auth.valkey.client import valkey_client

PASSWORD = "StrongPass123!"


def _unique_email(prefix: str = "sessioncleanuptest") -> str:
    return f"{prefix}-{uuid.uuid4().hex}@example.com"


async def _new_client() -> AsyncClient:
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="https://testserver", follow_redirects=False)


async def _signup_and_verify(client, created_emails, email):
    signup_resp = await client.post(
        "/auth/signup", json={"name": "Session Cleanup Test User", "email": email, "password": PASSWORD}
    )
    assert signup_resp.status_code == 200
    created_emails.append(email)

    token = await account_verification_service.create_verification_token(email)
    await valkey_client.set(f"verify:{token}", "1", ex=600)
    verify_resp = await client.post("/auth/verify-account", json={"token": token})
    assert verify_resp.status_code == 200


async def _session_row_count(email: str) -> int:
    async with database.async_session() as session:
        result = await session.execute(
            text(
                "SELECT count(*) FROM user_sessions WHERE user_id = "
                "(SELECT id FROM users WHERE email = :email)"
            ),
            {"email": email},
        )
        return result.scalar_one()


async def _age_every_session(email: str, expires_at: datetime) -> None:
    """Backdates every session row's expires_at directly, so a test can
    place a session past the retention cutoff without waiting real hours."""
    async with database.async_session() as session:
        await session.execute(
            text(
                "UPDATE user_sessions SET expires_at = :expires_at WHERE user_id = "
                "(SELECT id FROM users WHERE email = :email)"
            ),
            {"expires_at": expires_at, "email": email},
        )
        await session.commit()


@pytest_asyncio.fixture(autouse=True)
async def _cleanup_sessions_and_audit_log(created_emails):
    yield
    if not created_emails:
        return
    async with database.async_session() as session:
        await session.execute(
            text(
                "DELETE FROM user_sessions WHERE user_id IN "
                "(SELECT id FROM users WHERE email = ANY(:emails))"
            ),
            {"emails": created_emails},
        )
        await session.execute(
            text("DELETE FROM security_audit_log WHERE user_email = ANY(:emails)"),
            {"emails": created_emails},
        )
        await session.commit()


@pytest.mark.asyncio
async def test_revoking_a_session_deletes_the_row_entirely(client, created_emails):
    email = _unique_email()
    await _signup_and_verify(client, created_emails, email)
    await client.post("/auth/login", json={"email": email, "password": PASSWORD})

    other_device = await _new_client()
    try:
        await other_device.post("/auth/login", json={"email": email, "password": PASSWORD})
        assert await _session_row_count(email) == 2

        sessions = (await client.get("/auth/sessions")).json()
        other_session = next(s for s in sessions if not s["is_current"])
        revoke_resp = await client.delete(f"/auth/sessions/{other_session['id']}")
        assert revoke_resp.status_code == 200

        # The row is gone, not left behind with revoked_at set.
        assert await _session_row_count(email) == 1
    finally:
        await other_device.aclose()


@pytest.mark.asyncio
async def test_logout_deletes_only_the_callers_own_row(client, created_emails):
    email = _unique_email()
    await _signup_and_verify(client, created_emails, email)
    await client.post("/auth/login", json={"email": email, "password": PASSWORD})

    other_device = await _new_client()
    try:
        await other_device.post("/auth/login", json={"email": email, "password": PASSWORD})
        assert await _session_row_count(email) == 2

        logout_resp = await client.post("/auth/logout")
        assert logout_resp.status_code == 200

        assert await _session_row_count(email) == 1
    finally:
        await other_device.aclose()


@pytest.mark.asyncio
async def test_logout_all_deletes_every_row_for_the_user(client, created_emails):
    email = _unique_email()
    await _signup_and_verify(client, created_emails, email)
    await client.post("/auth/login", json={"email": email, "password": PASSWORD})

    other_device = await _new_client()
    try:
        await other_device.post("/auth/login", json={"email": email, "password": PASSWORD})
        assert await _session_row_count(email) == 2

        logout_all_resp = await client.post("/auth/logout/all")
        assert logout_all_resp.status_code == 200

        assert await _session_row_count(email) == 0
    finally:
        await other_device.aclose()


@pytest.mark.asyncio
async def test_purge_job_deletes_only_sessions_past_the_retention_cutoff(client, created_emails, mocker):
    mocker.patch(
        "backend.mystic_auth.procrastinate_tasks.session_cleanup_tasks.settings.SESSION_ROW_RETENTION_HOURS", 1
    )

    expired_email = _unique_email("expired")
    recent_email = _unique_email("recent")
    await _signup_and_verify(client, created_emails, expired_email)
    await client.post("/auth/login", json={"email": expired_email, "password": PASSWORD})

    other_client = await _new_client()
    try:
        await _signup_and_verify(other_client, created_emails, recent_email)
        await other_client.post("/auth/login", json={"email": recent_email, "password": PASSWORD})

        # Past the 1-hour retention cutoff: swept.
        await _age_every_session(expired_email, datetime.now(UTC) - timedelta(hours=2))
        # A freshly-minted session's real expires_at (access/refresh token
        # lifetime) is always well beyond 1 hour ago: left untouched.

        deleted_count = await purge_expired_sessions(timestamp=0)
        assert deleted_count == 1

        assert await _session_row_count(expired_email) == 0
        assert await _session_row_count(recent_email) == 1
    finally:
        await other_client.aclose()


@pytest.mark.asyncio
async def test_purge_job_returns_zero_when_nothing_has_expired(client, created_emails):
    email = _unique_email()
    await _signup_and_verify(client, created_emails, email)
    await client.post("/auth/login", json={"email": email, "password": PASSWORD})

    deleted_count = await purge_expired_sessions(timestamp=0)

    assert deleted_count == 0
    assert await _session_row_count(email) == 1
