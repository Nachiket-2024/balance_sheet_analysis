# tests/backend/mystic_auth/integration/user_session/test_session_geolocation_integration.py
#
# End-to-end coverage for the Manage Sessions "Location" column: city/
# country resolved from the login IP via session_geolocation.py and
# surfaced on GET /auth/sessions. GEOIP_DB_PATH is unset in this test
# environment (no .mmdb file in CI), so resolve_city_country is patched
# at its session_service import site to prove the plumbing end to end
# (session_service -> session_repository -> UserSession.city/country ->
# SessionRead). A second, unpatched test covers the real fail-open
# behavior when geolocation is disabled.
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import text

from backend.mystic_auth.auth.verify_account.account_verification_service import (
    account_verification_service,
)
from backend.mystic_auth.database.connection import database
from backend.mystic_auth.valkey.client import valkey_client

PASSWORD = "StrongPass123!"


def _unique_email(prefix: str = "geosessiontest") -> str:
    return f"{prefix}-{uuid.uuid4().hex}@example.com"


async def _signup_and_verify(client, created_emails, email):
    signup_resp = await client.post(
        "/auth/signup", json={"name": "Geo Session Test User", "email": email, "password": PASSWORD}
    )
    assert signup_resp.status_code == 200
    created_emails.append(email)

    token = await account_verification_service.create_verification_token(email)
    await valkey_client.set(f"verify:{token}", "1", ex=600)
    verify_resp = await client.post("/auth/verify-account", json={"token": token})
    assert verify_resp.status_code == 200


@pytest_asyncio.fixture(autouse=True)
async def _cleanup_sessions(created_emails):
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
        await session.commit()


@pytest.mark.asyncio
async def test_login_with_geolocation_available_surfaces_city_and_country(client, created_emails, mocker):
    mocker.patch(
        "backend.mystic_auth.user_session.session_service.resolve_city_country",
        return_value=("Mumbai", "India"),
    )
    email = _unique_email()
    await _signup_and_verify(client, created_emails, email)

    login_resp = await client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert login_resp.status_code == 200

    sessions = (await client.get("/auth/sessions")).json()
    assert len(sessions) == 1
    assert sessions[0]["city"] == "Mumbai"
    assert sessions[0]["country"] == "India"


@pytest.mark.asyncio
async def test_login_with_geolocation_disabled_leaves_city_and_country_null(client, created_emails):
    # GEOIP_DB_PATH is unset in this test environment - the real,
    # unpatched fail-open path (see session_geolocation.py), not a mock.
    email = _unique_email()
    await _signup_and_verify(client, created_emails, email)

    login_resp = await client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert login_resp.status_code == 200

    sessions = (await client.get("/auth/sessions")).json()
    assert len(sessions) == 1
    assert sessions[0]["city"] is None
    assert sessions[0]["country"] is None
