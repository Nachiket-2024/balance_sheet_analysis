# tests/backend/mystic_auth/integration/test_refresh_token_integration.py
#
# End-to-end refresh-token rotation/reuse-detection coverage, and the
# real-time session-events (SSE) route's auth gate, against the real ASGI
# app, real PostgreSQL, and real Redis (see conftest.py). Split out of what
# used to be one 799-line test_auth_api_integration.py. Unlike the mocked
# unit suite, these exercise the actual Redis atomicity behavior (claim_jti_
# for_rotation's SET...NX) that mocks cannot surface.
import asyncio
import uuid
from datetime import UTC, datetime, timedelta

import jwt as pyjwt
import pytest
from backend.mystic_auth.core.settings import settings

from .auth_test_accounts import (
    PASSWORD,
    TEST_COOKIE_DOMAIN,
    refresh_with_cookie,
    signup_verify_login,
    unique_email,
)

# ---------------------------- refresh rotation / reuse detection ----------------------------

@pytest.mark.asyncio
async def test_refresh_token_rotates_and_old_token_is_rejected(client, created_emails):
    email = unique_email()
    login_resp = await signup_verify_login(client, created_emails, email)
    old_refresh = login_resp.cookies["refresh_token"]

    refresh_resp = await refresh_with_cookie(client, old_refresh)
    assert refresh_resp.status_code == 200
    new_refresh = refresh_resp.cookies["refresh_token"]
    assert new_refresh != old_refresh

    reuse_resp = await refresh_with_cookie(client, old_refresh)
    assert reuse_resp.status_code == 401


@pytest.mark.asyncio
async def test_concurrent_refresh_with_the_same_token_only_one_succeeds(client, created_emails):
    # Regression guard for the refresh-token double-spend race: two requests
    # firing concurrently with the identical still-valid refresh token must
    # not both be able to rotate it into a new pair: claim_jti_for_rotation's
    # atomic Redis SET...NX means only one can ever win, regardless of how
    # the two requests interleave.
    email = unique_email()
    login_resp = await signup_verify_login(client, created_emails, email)
    refresh_token = login_resp.cookies["refresh_token"]

    client.cookies.set("refresh_token", refresh_token, domain=TEST_COOKIE_DOMAIN, path="/auth")
    responses = await asyncio.gather(
        client.post("/auth/refresh/"),
        client.post("/auth/refresh/"),
    )

    statuses = sorted(resp.status_code for resp in responses)
    # Exactly one of the two concurrent requests may win the claim; the
    # other loses the atomic SET...NX and is treated as reuse (401).
    assert statuses == [200, 401]


@pytest.mark.asyncio
async def test_refresh_token_reuse_revokes_the_compromised_chain_only(client, created_emails):
    """Reuse detection must kill the entire compromised rotation chain
    (device A's own current, already-rotated-forward token included: it
    might be the attacker's copy, not the legitimate client's), but must
    leave a genuinely independent session (device B: a separate login, a
    separate chain) alone. An earlier version revoked every session on the
    account unconditionally, which meant a stale/already-revoked token
    being replayed on ANY device (e.g. an old tab retrying after an
    intentional logout-all elsewhere) could also kill an unrelated,
    never-compromised session created afterward - see
    docs/mystic_auth/authentication/session-management.md."""
    email = unique_email()
    login_resp = await signup_verify_login(client, created_emails, email)
    device_a_refresh = login_resp.cookies["refresh_token"]

    # A second, independent session/device for the same user: its own login,
    # its own rotation chain, sharing nothing with device A's.
    second_login = await client.post("/auth/login", json={"email": email, "password": PASSWORD})
    device_b_refresh = second_login.cookies["refresh_token"]

    # Rotate device A forward once (the legitimate use) - its current,
    # descendant token, still part of the SAME chain as the one about to be
    # replayed - then replay the original, now-revoked device A token,
    # simulating a stolen refresh token being used after the real client
    # already rotated it.
    rotate_resp = await refresh_with_cookie(client, device_a_refresh)
    device_a_rotated_refresh = rotate_resp.cookies["refresh_token"]
    reuse_resp = await refresh_with_cookie(client, device_a_refresh)
    assert reuse_resp.status_code == 401

    # The compromised chain is fully killed: both the reused token itself
    # (already asserted above) and its legitimate-looking rotated
    # descendant, since there is no way to tell from the registry alone
    # which of the two is the attacker's copy.
    device_a_rotated_resp = await refresh_with_cookie(client, device_a_rotated_refresh)
    assert device_a_rotated_resp.status_code == 401

    # Device B never shared this chain and must be entirely unaffected.
    device_b_resp = await refresh_with_cookie(client, device_b_refresh)
    assert device_b_resp.status_code == 200


@pytest.mark.asyncio
async def test_refresh_rejects_access_token_type(client, created_emails):
    email = unique_email()
    login_resp = await signup_verify_login(client, created_emails, email)
    access_token = login_resp.cookies["access_token"]

    resp = await refresh_with_cookie(client, access_token)

    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_refresh_rejects_an_actually_expired_token(client, created_emails):
    # Regression guard: existing refresh-token tests only ever mock
    # decode_payload directly, never exercising PyJWT's own exp check. A
    # genuinely expired (but otherwise validly-signed) refresh token must
    # be rejected the same generic way as a tampered one, deliberately
    # indistinguishable, per refresh_token_handler.py's anti-enumeration
    # comment, but this at least confirms the expiry path is reached at
    # all and doesn't crash or behave differently.
    email = unique_email()
    await signup_verify_login(client, created_emails, email)

    expired_payload = {
        "email": email,
        "type": "refresh",
        "jti": uuid.uuid4().hex,
        "exp": datetime.now(UTC) - timedelta(minutes=1),
    }
    expired_token = pyjwt.encode(expired_payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

    resp = await refresh_with_cookie(client, expired_token)

    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_repeated_legitimate_refreshes_do_not_trip_failed_attempt_lockout(client, created_emails):
    # Regression guard (real Redis): rate_key and lock_key previously
    # collided ("refresh:ip:{ip}" for both), so rate_limiter_service's
    # per-request counter (incremented on every call, success or failure)
    # and login_protection_service's failure counter shared one key:
    # a handful of legitimate token rotations alone could trip the
    # 5-failed-attempt lockout with zero real failures. Chain more than
    # MAX_FAILED_LOGIN_ATTEMPTS consecutive legitimate rotations and confirm
    # every single one succeeds.
    email = unique_email()
    login_resp = await signup_verify_login(client, created_emails, email)
    refresh_token = login_resp.cookies["refresh_token"]

    for _ in range(settings.MAX_FAILED_LOGIN_ATTEMPTS + 2):
        resp = await refresh_with_cookie(client, refresh_token)
        assert resp.status_code == 200
        refresh_token = resp.cookies["refresh_token"]


@pytest.mark.asyncio
async def test_refresh_token_cookie_is_scoped_to_auth_path(client, created_emails):
    # Real end-to-end check (real cookie jar, real Set-Cookie parsing) that
    # refresh_token is scoped to /auth, unlike access_token, which stays
    # site-wide since /users/* routes need it too.
    email = unique_email()
    await signup_verify_login(client, created_emails, email)

    cookies_by_name = {cookie.name: cookie for cookie in client.cookies.jar}
    assert cookies_by_name["refresh_token"].path == "/auth"
    assert cookies_by_name["access_token"].path == "/"


# ---------------------------- real-time session events (SSE) ----------------------------
# The stream itself (real Redis Pub/Sub, heartbeats, disconnect handling) is
# exercised directly against user_session/session_events.py in
# tests/backend/mystic_auth/unit/user_session/test_session_events_unit.py, and
# the end-to-end publish-on-revoke wiring in
# test_manage_sessions_integration.py, not here: httpx's ASGITransport test
# harness doesn't reliably support this endpoint's held-open streaming
# response at all (even opening one with nothing else going on hangs
# indefinitely), so trying to drive it through this specific test client is
# fighting the harness, not testing real behavior. What's left worth
# confirming at the route level, without actually opening the stream, is
# that auth is enforced.

@pytest.mark.asyncio
async def test_session_events_stream_requires_authentication(client, created_emails):
    resp = await client.get("/auth/session-events")

    assert resp.status_code == 401
