# tests/backend/mystic_auth/integration/auth/test_password_reset_integration.py
#
# End-to-end password-reset coverage against the real ASGI app, real
# PostgreSQL, and real Valkey (see conftest.py).
import asyncio

import pytest

from backend.mystic_auth.auth.password_logic.password_service import (
    password_service,
)
from backend.mystic_auth.core.settings import settings
from backend.mystic_auth.valkey.client import valkey_client

from .auth_test_accounts import (
    PASSWORD,
    refresh_with_cookie,
    signup_verify_login,
    unique_email,
)

# ---------------------------- password reset ----------------------------

async def _request_password_reset(client, email: str) -> str:
    """Mirrors password_reset_service.send_reset_email's Valkey single-use
    registration so the test can drive password-reset/confirm without
    depending on the email worker being up to deliver the link."""
    resp = await client.post("/auth/password-reset/request", json={"email": email})
    assert resp.status_code == 200

    token = await password_service.create_reset_token(email)
    await valkey_client.set(f"password_reset:{token}", "1", ex=settings.RESET_TOKEN_EXPIRE_MINUTES * 60)
    return token


@pytest.mark.asyncio
async def test_password_reset_revokes_existing_sessions(client, created_emails):
    email = unique_email()
    login_resp = await signup_verify_login(client, created_emails, email)
    old_refresh = login_resp.cookies["refresh_token"]

    new_password = "EvenStrongerPass456!"
    reset_token = await _request_password_reset(client, email)

    confirm_resp = await client.post(
        "/auth/password-reset/confirm", json={"token": reset_token, "new_password": new_password}
    )
    assert confirm_resp.status_code == 200

    # A stolen refresh token from before the reset must no longer work
    # afterwards.
    reuse_resp = await refresh_with_cookie(client, old_refresh)
    assert reuse_resp.status_code == 401

    # New credentials work; old ones don't.
    old_login = await client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert old_login.status_code == 401
    new_login = await client.post("/auth/login", json={"email": email, "password": new_password})
    assert new_login.status_code == 200


@pytest.mark.asyncio
async def test_password_reset_token_is_single_use(client, created_emails):
    email = unique_email()
    await signup_verify_login(client, created_emails, email)

    reset_token = await _request_password_reset(client, email)

    first = await client.post(
        "/auth/password-reset/confirm",
        json={"token": reset_token, "new_password": "FirstNewPass123!"},
    )
    second = await client.post(
        "/auth/password-reset/confirm",
        json={"token": reset_token, "new_password": "SecondNewPass456!"},
    )

    assert first.status_code == 200
    assert second.status_code != 200


@pytest.mark.asyncio
async def test_password_reset_survives_retry_after_weak_password(client, created_emails):
    # Regression guard for the TOCTOU fix: a recoverable validation failure
    # (weak password) must restore the token rather than permanently
    # consuming it, otherwise a user who mistypes a weak password on their
    # first attempt would be locked out of their own valid reset link.
    email = unique_email()
    await signup_verify_login(client, created_emails, email)
    reset_token = await _request_password_reset(client, email)

    weak_resp = await client.post(
        "/auth/password-reset/confirm", json={"token": reset_token, "new_password": "weak"}
    )
    assert weak_resp.status_code != 200

    retry_resp = await client.post(
        "/auth/password-reset/confirm",
        json={"token": reset_token, "new_password": "StrongRetryPass789!"},
    )
    assert retry_resp.status_code == 200

    login_resp = await client.post(
        "/auth/login", json={"email": email, "password": "StrongRetryPass789!"}
    )
    assert login_resp.status_code == 200


@pytest.mark.asyncio
async def test_password_reset_concurrent_requests_only_one_succeeds(client, created_emails):
    # The core TOCTOU race (real Valkey, real Postgres): two requests firing
    # concurrently with the same valid token and different new passwords
    # must not both succeed. GETDEL's atomicity means only one can ever win
    # the single-use check, regardless of how the DB writes interleave.
    email = unique_email()
    await signup_verify_login(client, created_emails, email)
    reset_token = await _request_password_reset(client, email)

    responses = await asyncio.gather(
        client.post(
            "/auth/password-reset/confirm",
            json={"token": reset_token, "new_password": "ConcurrentPassA1!"},
        ),
        client.post(
            "/auth/password-reset/confirm",
            json={"token": reset_token, "new_password": "ConcurrentPassB2!"},
        ),
    )

    statuses = sorted(resp.status_code for resp in responses)
    # Exactly one of the two concurrent requests may succeed; the other loses
    # the atomic action reservation and is rejected without mutating state.
    assert statuses == [200, 429]

    # Confirm exactly one of the two candidate passwords actually works.
    login_a = await client.post("/auth/login", json={"email": email, "password": "ConcurrentPassA1!"})
    login_b = await client.post("/auth/login", json={"email": email, "password": "ConcurrentPassB2!"})
    assert sorted([login_a.status_code, login_b.status_code]) == [200, 401]
