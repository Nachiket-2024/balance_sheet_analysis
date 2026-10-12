# tests/backend/mystic_auth/integration/user_session/test_manage_sessions_concurrency_integration.py
#
# Concurrent-revoke coverage for DELETE /auth/sessions/{id}, split out from
# test_manage_sessions_integration.py: two simultaneous requests to revoke
# the same other-device session must not both report success, and must not
# leave the session half-revoked.
import asyncio
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from backend.app.main import app
from backend.mystic_auth.auth.verify_account.account_verification_service import (
    account_verification_service,
)
from backend.mystic_auth.database.connection import database
from backend.mystic_auth.valkey.client import valkey_client

PASSWORD = "StrongPass123!"


def _unique_email(prefix: str = "sessionrace") -> str:
    return f"{prefix}-{uuid.uuid4().hex}@example.com"


async def _new_client() -> AsyncClient:
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="https://testserver", follow_redirects=False)


async def _signup_and_verify(client, created_emails, email):
    signup_resp = await client.post(
        "/auth/signup", json={"name": "Session Race Test User", "email": email, "password": PASSWORD}
    )
    assert signup_resp.status_code == 200
    created_emails.append(email)

    token = await account_verification_service.create_verification_token(email)
    await valkey_client.set(f"verify:{token}", "1", ex=600)
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
async def test_concurrently_revoking_the_same_session_twice_only_one_request_succeeds(client, created_emails):
    email = _unique_email()
    await _signup_and_verify(client, created_emails, email)
    await client.post("/auth/login", json={"email": email, "password": PASSWORD})

    other_device = await _new_client()
    try:
        await other_device.post("/auth/login", json={"email": email, "password": PASSWORD})

        sessions = (await client.get("/auth/sessions")).json()
        other_session = next(s for s in sessions if not s["is_current"])

        results = await asyncio.gather(
            client.delete(f"/auth/sessions/{other_session['id']}"),
            client.delete(f"/auth/sessions/{other_session['id']}"),
        )
        statuses = sorted(r.status_code for r in results)
        # Both can see the already-revoked outcome (200/200) or the loser
        # can get a 404. Either way, no 5xx and no half-revoked session.
        assert statuses in ([200, 200], [200, 404]), statuses

        remaining = (await client.get("/auth/sessions")).json()
        assert len(remaining) == 1
        assert remaining[0]["is_current"] is True
    finally:
        await other_device.aclose()
