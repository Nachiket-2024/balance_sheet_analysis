# tests/backend/mystic_auth/integration/test_manage_sessions_integration.py
#
# End-to-end coverage for the "Manage Sessions" feature (GET /auth/sessions,
# DELETE /auth/sessions/{id}, backed by user_session/session_service.py and
# auth/manage_sessions/*) against the real ASGI app, real PostgreSQL, and
# real Redis. Mirrors test_audit_log_integration.py's fixture/cleanup style.
import json
import uuid

import pytest
import pytest_asyncio
from backend.app.main import app
from backend.mystic_auth.auth.verify_account.account_verification_service import (
    account_verification_service,
)
from backend.mystic_auth.database.connection import database
from backend.mystic_auth.redis.client import redis_client
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

PASSWORD = "StrongPass123!"


def _unique_email(prefix: str = "sessiontest") -> str:
    return f"{prefix}-{uuid.uuid4().hex}@example.com"


async def _new_client() -> AsyncClient:
    """A second, independently-cookied client hitting the same in-process
    app, standing in for a second device/browser signed into the same
    account."""
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="https://testserver", follow_redirects=False)


async def _signup_and_verify(client, created_emails, email):
    signup_resp = await client.post(
        "/auth/signup", json={"name": "Session Test User", "email": email, "password": PASSWORD}
    )
    assert signup_resp.status_code == 200
    created_emails.append(email)

    token = await account_verification_service.create_verification_token(email)
    await redis_client.set(f"verify:{token}", "1", ex=600)
    verify_resp = await client.post("/auth/verify-account", json={"token": token})
    assert verify_resp.status_code == 200


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
async def test_unauthenticated_request_to_list_sessions_is_rejected(client):
    resp = await client.get("/auth/sessions")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_creates_a_session_visible_via_list_sessions(client, created_emails):
    email = _unique_email()
    await _signup_and_verify(client, created_emails, email)

    login_resp = await client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert login_resp.status_code == 200

    list_resp = await client.get("/auth/sessions")
    assert list_resp.status_code == 200
    sessions = list_resp.json()
    assert len(sessions) == 1
    assert sessions[0]["is_current"] is True
    assert sessions[0]["ip_address"] is not None


@pytest.mark.asyncio
async def test_a_second_login_from_another_client_shows_two_sessions_with_exactly_one_current(
    client, created_emails
):
    email = _unique_email()
    await _signup_and_verify(client, created_emails, email)

    login_resp = await client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert login_resp.status_code == 200

    other_device = await _new_client()
    try:
        other_login_resp = await other_device.post("/auth/login", json={"email": email, "password": PASSWORD})
        assert other_login_resp.status_code == 200

        list_from_device_a = (await client.get("/auth/sessions")).json()
        list_from_device_b = (await other_device.get("/auth/sessions")).json()

        assert len(list_from_device_a) == 2
        assert len(list_from_device_b) == 2
        assert sum(1 for s in list_from_device_a if s["is_current"]) == 1
        assert sum(1 for s in list_from_device_b if s["is_current"]) == 1
        # Different clients must disagree on which row is "current".
        current_a = next(s["id"] for s in list_from_device_a if s["is_current"])
        current_b = next(s["id"] for s in list_from_device_b if s["is_current"])
        assert current_a != current_b
    finally:
        await other_device.aclose()


@pytest.mark.asyncio
async def test_revoking_another_devices_session_ends_it_and_writes_an_audit_event(client, created_emails):
    email = _unique_email()
    await _signup_and_verify(client, created_emails, email)
    await client.post("/auth/login", json={"email": email, "password": PASSWORD})

    other_device = await _new_client()
    try:
        await other_device.post("/auth/login", json={"email": email, "password": PASSWORD})

        sessions = (await client.get("/auth/sessions")).json()
        other_session = next(s for s in sessions if not s["is_current"])

        revoke_resp = await client.delete(f"/auth/sessions/{other_session['id']}")
        assert revoke_resp.status_code == 200

        remaining = (await client.get("/auth/sessions")).json()
        assert len(remaining) == 1
        assert remaining[0]["is_current"] is True

        log_resp = await client.get("/audit/security-log/me", params={"event_type": "session_revoked"})
        assert log_resp.status_code == 200
        assert len(log_resp.json()) == 1
    finally:
        await other_device.aclose()


@pytest.mark.asyncio
async def test_revoking_another_devices_session_publishes_a_real_time_event(client, created_emails):
    """The device actually being revoked - not the caller doing the
    revoking - is the one that needs to find out immediately (see
    user_session/session_events.py). Subscribes directly via redis-py's own
    Pub/Sub client, the same channel GET /auth/session-events streams from,
    rather than going through that endpoint's httpx streaming response:
    httpx's ASGITransport test harness doesn't reliably support a held-open
    streaming GET racing a second concurrent request the way a real ASGI
    server does, so this checks the actual Redis-level side effect instead.
    See test_session_events_unit.py for the endpoint/generator's own
    behavior."""
    email = _unique_email()
    await _signup_and_verify(client, created_emails, email)
    await client.post("/auth/login", json={"email": email, "password": PASSWORD})

    other_device = await _new_client()
    try:
        await other_device.post("/auth/login", json={"email": email, "password": PASSWORD})

        pubsub = redis_client.pubsub()
        await pubsub.subscribe(f"session_events:{email}")
        try:
            # Drains the subscription-confirmation message so the next one
            # read below is the actual push, not this bookkeeping message.
            await pubsub.get_message(ignore_subscribe_messages=True, timeout=1)

            sessions = (await client.get("/auth/sessions")).json()
            other_session = next(s for s in sessions if not s["is_current"])
            revoke_resp = await client.delete(f"/auth/sessions/{other_session['id']}")
            assert revoke_resp.status_code == 200

            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=5)
            assert message is not None
            assert json.loads(message["data"]) == {"type": "revoked"}
        finally:
            await pubsub.unsubscribe(f"session_events:{email}")
            await pubsub.aclose()
    finally:
        await other_device.aclose()


@pytest.mark.asyncio
async def test_reusing_a_revoked_sessions_refresh_token_stays_scoped_to_that_session(client, created_emails):
    """A per-session revoke bumps that one device's chain version
    (session_service.revoke_one_session), so its refresh token is rejected
    on its very next use - but as a plain "this session is no longer
    current" (jwt_service.is_current_version, checked before rotation ever
    reaches reuse-detection), not as suspected theft. Only a token that
    gets *reused after successfully rotating* looks like replay; a device
    that was simply revoked and never touched its refresh token again
    never reaches that path at all, so the caller's own session (and
    everything else on the account) must be completely unaffected."""
    email = _unique_email()
    await _signup_and_verify(client, created_emails, email)
    await client.post("/auth/login", json={"email": email, "password": PASSWORD})

    other_device = await _new_client()
    try:
        await other_device.post("/auth/login", json={"email": email, "password": PASSWORD})

        sessions = (await client.get("/auth/sessions")).json()
        other_session = next(s for s in sessions if not s["is_current"])
        await client.delete(f"/auth/sessions/{other_session['id']}")

        refresh_resp = await other_device.post("/auth/refresh/")
        assert refresh_resp.status_code == 401

        # The caller's own session is completely untouched: this is not
        # account-wide reuse-detection, just that one revoked device's
        # session ending.
        remaining_resp = await client.get("/auth/sessions")
        assert remaining_resp.status_code == 200
        remaining = remaining_resp.json()
        assert len(remaining) == 1
        assert remaining[0]["is_current"] is True
    finally:
        await other_device.aclose()


@pytest.mark.asyncio
async def test_revoking_the_callers_own_current_session_is_rejected(client, created_emails):
    email = _unique_email()
    await _signup_and_verify(client, created_emails, email)
    await client.post("/auth/login", json={"email": email, "password": PASSWORD})

    sessions = (await client.get("/auth/sessions")).json()
    own_session_id = sessions[0]["id"]

    resp = await client.delete(f"/auth/sessions/{own_session_id}")
    assert resp.status_code == 400

    # Rejected, not revoked: the session must still be listed afterward.
    still_listed = (await client.get("/auth/sessions")).json()
    assert len(still_listed) == 1


@pytest.mark.asyncio
async def test_revoking_a_nonexistent_session_returns_404(client, created_emails):
    email = _unique_email()
    await _signup_and_verify(client, created_emails, email)
    await client.post("/auth/login", json={"email": email, "password": PASSWORD})

    resp = await client.delete("/auth/sessions/999999999")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_cannot_revoke_another_users_session(client, created_emails):
    email_a = _unique_email("a")
    email_b = _unique_email("b")
    await _signup_and_verify(client, created_emails, email_a)
    await client.post("/auth/login", json={"email": email_a, "password": PASSWORD})
    victim_session_id = (await client.get("/auth/sessions")).json()[0]["id"]

    other_device = await _new_client()
    try:
        await _signup_and_verify(other_device, created_emails, email_b)
        await other_device.post("/auth/login", json={"email": email_b, "password": PASSWORD})

        resp = await other_device.delete(f"/auth/sessions/{victim_session_id}")
        assert resp.status_code == 404

        # Victim's session must be untouched.
        still_there = (await client.get("/auth/sessions")).json()
        assert len(still_there) == 1
    finally:
        await other_device.aclose()


@pytest.mark.asyncio
async def test_logout_removes_the_session_from_the_active_list(client, created_emails):
    email = _unique_email()
    await _signup_and_verify(client, created_emails, email)
    await client.post("/auth/login", json={"email": email, "password": PASSWORD})

    assert len((await client.get("/auth/sessions")).json()) == 1

    logout_resp = await client.post("/auth/logout")
    assert logout_resp.status_code == 200

    # Cookies are cleared by logout, so re-authenticate to inspect the list.
    await client.post("/auth/login", json={"email": email, "password": PASSWORD})
    sessions_after = (await client.get("/auth/sessions")).json()
    assert len(sessions_after) == 1
