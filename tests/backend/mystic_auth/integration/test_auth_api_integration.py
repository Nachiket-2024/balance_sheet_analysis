# tests/backend/mystic_auth/integration/test_auth_api_integration.py
#
# End-to-end auth flows against the real ASGI app, real PostgreSQL, and real
# Redis (see conftest.py). Unlike the mocked unit suite, these exercise the
# actual Redis type/atomicity behavior and actual DB commits, the class of
# bug (e.g. a Set/Hash key-type collision, or a missing session-revocation
# call) that mocks cannot surface.
import asyncio
import statistics
import time
import uuid
from datetime import UTC, datetime, timedelta

import jwt as pyjwt
import pytest
from backend.mystic_auth.auth.verify_account.account_verification_service import account_verification_service
from backend.mystic_auth.core.settings import settings
from backend.mystic_auth.redis.client import redis_client

PASSWORD = "StrongPass123!"


def _unique_email() -> str:
    return f"inttest-{uuid.uuid4().hex}@example.com"


# conftest.py's `client` fixture uses base_url="https://testserver", a
# dotless hostname, which CPython's http.cookiejar (what httpx's cookie jar
# is built on) normalizes to "testserver.local" internally for matching
# purposes. Cookies set manually here must match that (domain, path, name)
# key exactly, or they land as a second, separate jar entry instead of
# overwriting the real one from a prior response: see
# _refresh_with_cookie's docstring below for why that matters.
_TEST_COOKIE_DOMAIN = "testserver.local"


async def _refresh_with_cookie(client, refresh_token: str):
    """Calls /auth/refresh/ with an explicit refresh_token cookie value,
    independent of whatever the client's shared cookie jar currently holds,
    needed to simulate stale/reused/forged/cross-session tokens. httpx
    deprecated per-request `cookies=` in favor of setting cookies on the
    client itself, hence setting it here rather than passing `cookies=`.
    Both domain and path must match the real cookie's (see
    _TEST_COOKIE_DOMAIN above): the jar keys cookies by (domain, path,
    name), so an inexact match creates a second entry alongside the real one
    instead of overwriting it, which then survives the endpoint's own
    cookie-clearing response untouched."""
    client.cookies.set("refresh_token", refresh_token, domain=_TEST_COOKIE_DOMAIN, path="/auth")
    return await client.post("/auth/refresh/")


async def _signup_verify_login(client, created_emails, email: str, password: str = PASSWORD):
    """Shared setup: create a verified user and log in, returning the
    logged-in client (cookies persist on the client's cookie jar)."""
    signup_resp = await client.post(
        "/auth/signup", json={"name": "Test User", "email": email, "password": password}
    )
    assert signup_resp.status_code == 200
    created_emails.append(email)

    # Verify via a real single-use Redis-backed token, the same way
    # account_verification_service.send_verification_email would, without
    # depending on the Taskiq email worker actually being up.
    token = await account_verification_service.create_verification_token(email)
    await redis_client.set(f"verify:{token}", "1", ex=600)
    verify_resp = await client.post("/auth/verify-account", json={"token": token})
    assert verify_resp.status_code == 200

    login_resp = await client.post("/auth/login", json={"email": email, "password": password})
    assert login_resp.status_code == 200
    return login_resp


# ---------------------------- signup / verify / login ----------------------------

@pytest.mark.asyncio
async def test_signup_verify_login_issues_working_session(client, created_emails):
    email = _unique_email()
    login_resp = await _signup_verify_login(client, created_emails, email)

    assert "access_token" in login_resp.cookies
    assert "refresh_token" in login_resp.cookies

    me_resp = await client.get("/auth/me")
    assert me_resp.status_code == 200
    assert me_resp.json()["email"] == email


@pytest.mark.asyncio
async def test_auth_me_exposes_permissions_matching_the_users_role(client, created_emails):
    # Regression guard for the PBAC contract: GET /auth/me must expose the
    # caller's resolved permission set (not just their role string), so
    # clients can make authorization-adjacent decisions by checking
    # permissions instead of hardcoding role-name comparisons. Exercised
    # against the real app/DB/JWT, a plain "user" account should get only
    # the self-service baseline, with no admin-only permission granted.
    email = _unique_email()
    login_resp = await _signup_verify_login(client, created_emails, email)
    assert login_resp.status_code == 200

    me_resp = await client.get("/auth/me")
    assert me_resp.status_code == 200
    body = me_resp.json()
    assert body["role"] == "user"
    assert body["permissions"] == ["users:read_own", "users:update_own"]


@pytest.mark.asyncio
async def test_login_before_verification_is_rejected(client, created_emails):
    email = _unique_email()
    signup_resp = await client.post(
        "/auth/signup", json={"name": "Unverified User", "email": email, "password": PASSWORD}
    )
    assert signup_resp.status_code == 200
    created_emails.append(email)

    login_resp = await client.post("/auth/login", json={"email": email, "password": PASSWORD})

    assert login_resp.status_code == 401
    assert "access_token" not in login_resp.cookies


@pytest.mark.asyncio
async def test_verification_token_is_single_use(client, created_emails):
    email = _unique_email()
    await client.post("/auth/signup", json={"name": "Test User", "email": email, "password": PASSWORD})
    created_emails.append(email)

    token = await account_verification_service.create_verification_token(email)
    await redis_client.set(f"verify:{token}", "1", ex=600)

    first = await client.post("/auth/verify-account", json={"token": token})
    second = await client.post("/auth/verify-account", json={"token": token})

    assert first.status_code == 200
    assert second.status_code != 200


@pytest.mark.asyncio
async def test_verify_account_no_longer_accepts_get_with_token_in_query_string(client, created_emails):
    # Regression guard: the verification token must never travel as a URL
    # query parameter: it ends up in browser history, server access logs,
    # and Referer headers. GET on this route must no longer work at all.
    email = _unique_email()
    await client.post("/auth/signup", json={"name": "Test User", "email": email, "password": PASSWORD})
    created_emails.append(email)

    token = await account_verification_service.create_verification_token(email)
    await redis_client.set(f"verify:{token}", "1", ex=600)

    get_resp = await client.get("/auth/verify-account", params={"token": token})
    assert get_resp.status_code == 405

    # The token must still be unconsumed: a rejected GET must not have
    # accidentally redeemed it, and a proper POST still works.
    post_resp = await client.post("/auth/verify-account", json={"token": token})
    assert post_resp.status_code == 200


@pytest.mark.asyncio
async def test_signup_rejects_oversized_password_with_422(client, created_emails):
    # Real end-to-end check that FastAPI's request-parsing layer enforces
    # the schema's max_length, not just the Pydantic model in isolation.
    resp = await client.post(
        "/auth/signup",
        json={"name": "Test User", "email": _unique_email(), "password": "a" * 129},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_signup_duplicate_email_does_not_create_second_user(client, created_emails):
    email = _unique_email()
    await client.post("/auth/signup", json={"name": "First", "email": email, "password": PASSWORD})
    created_emails.append(email)

    dup_resp = await client.post("/auth/signup", json={"name": "Second", "email": email, "password": PASSWORD})

    # Enumeration-resistant: same generic 200, but no second account was made
    # (verified by the original account's password still being the only valid one).
    assert dup_resp.status_code == 200
    token = await account_verification_service.create_verification_token(email)
    await redis_client.set(f"verify:{token}", "1", ex=600)
    await client.post("/auth/verify-account", json={"token": token})
    login_resp = await client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert login_resp.status_code == 200


@pytest.mark.asyncio
async def test_signup_duplicate_email_rejected_with_different_casing(client, created_emails):
    # User@Example.com and user@example.com must be the same account,
    # confirmed against the real DB unique constraint + normalization, not
    # mocks, since this is exactly the kind of boundary a mock could hide.
    email = _unique_email()
    mixed_case_email = email.replace("inttest-", "INTTEST-", 1)
    await client.post("/auth/signup", json={"name": "First", "email": email, "password": PASSWORD})
    created_emails.append(email)

    dup_resp = await client.post(
        "/auth/signup", json={"name": "Second", "email": mixed_case_email, "password": PASSWORD}
    )

    # Same generic 200 (enumeration-resistant), but no second account exists:
    # verified below by logging in with the mixed-case address and the
    # *original* account's password.
    assert dup_resp.status_code == 200
    token = await account_verification_service.create_verification_token(email)
    await redis_client.set(f"verify:{token}", "1", ex=600)
    await client.post("/auth/verify-account", json={"token": token})

    login_resp = await client.post(
        "/auth/login", json={"email": mixed_case_email, "password": PASSWORD}
    )
    assert login_resp.status_code == 200


@pytest.mark.asyncio
async def test_login_succeeds_with_different_casing_than_used_at_signup(client, created_emails):
    email = _unique_email()
    login_resp = await _signup_verify_login(client, created_emails, email)
    assert login_resp.status_code == 200

    mixed_case_email = email.upper()
    second_login_resp = await client.post(
        "/auth/login", json={"email": mixed_case_email, "password": PASSWORD}
    )
    assert second_login_resp.status_code == 200


# ---------------------------- login timing side-channel ----------------------------

async def _median_login_latency(client, email: str, password: str, samples: int = 9) -> float:
    durations = []
    for _ in range(samples):
        # Reset the lockout counter before every sample, otherwise repeated
        # wrong-password attempts against the same email trip
        # MAX_FAILED_LOGIN_ATTEMPTS partway through, and the locked-out
        # responses (which return instantly, before any hash comparison)
        # would corrupt this timing measurement rather than reflect it.
        await redis_client.delete(f"login_lock:email:{email}")
        start = time.perf_counter()
        await client.post("/auth/login", json={"email": email, "password": password})
        durations.append(time.perf_counter() - start)
        client.cookies.clear()
    return statistics.median(durations)


@pytest.mark.asyncio
async def test_login_timing_does_not_distinguish_nonexistent_from_wrong_password(client, created_emails):
    # Regression guard for the login timing side-channel (real Argon2, real
    # DB, a mocked test can't observe this since it doesn't perform real
    # hashing). Before the fix, "no such account" returned in a fraction of
    # the time "wrong password on a real, verified account" took, because
    # only the latter paid for an Argon2 comparison. Both must now cost
    # about the same, since both perform one.
    email = _unique_email()
    await _signup_verify_login(client, created_emails, email)
    client.cookies.clear()

    nonexistent_latency = await _median_login_latency(client, _unique_email(), "wrong-password")
    wrong_password_latency = await _median_login_latency(client, email, "wrong-password")

    # Generous tolerance to absorb normal jitter: the bug this guards
    # against produces an orders-of-magnitude gap (no hashing vs. real
    # Argon2), not a marginal one, so 3x is still a tight bound against it.
    assert nonexistent_latency < wrong_password_latency * 3
    assert wrong_password_latency < nonexistent_latency * 3


@pytest.mark.asyncio
async def test_login_timing_does_not_distinguish_unverified_from_wrong_password(client, created_emails):
    verified_email = _unique_email()
    await _signup_verify_login(client, created_emails, verified_email)
    client.cookies.clear()

    unverified_email = _unique_email()
    await client.post(
        "/auth/signup", json={"name": "Unverified", "email": unverified_email, "password": PASSWORD}
    )
    created_emails.append(unverified_email)

    unverified_latency = await _median_login_latency(client, unverified_email, "wrong-password")
    wrong_password_latency = await _median_login_latency(client, verified_email, "wrong-password")

    assert unverified_latency < wrong_password_latency * 3
    assert wrong_password_latency < unverified_latency * 3


# ---------------------------- login lockout (real Redis) ----------------------------

@pytest.mark.asyncio
async def test_login_locks_out_after_max_failed_attempts(client, created_emails):
    email = _unique_email()
    await _signup_verify_login(client, created_emails, email)
    client.cookies.clear()

    for _ in range(settings.MAX_FAILED_LOGIN_ATTEMPTS):
        resp = await client.post("/auth/login", json={"email": email, "password": "wrong-password"})
        assert resp.status_code == 401

    locked_resp = await client.post("/auth/login", json={"email": email, "password": "wrong-password"})
    assert locked_resp.status_code == 429

    # Even the correct password is rejected while locked out.
    still_locked_resp = await client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert still_locked_resp.status_code == 429


@pytest.mark.asyncio
async def test_successful_login_resets_failed_attempt_counter(client, created_emails):
    email = _unique_email()
    await _signup_verify_login(client, created_emails, email)
    client.cookies.clear()

    for _ in range(settings.MAX_FAILED_LOGIN_ATTEMPTS - 1):
        resp = await client.post("/auth/login", json={"email": email, "password": "wrong-password"})
        assert resp.status_code == 401

    success_resp = await client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert success_resp.status_code == 200

    # Counter was reset by the success, so a further failure shouldn't lock immediately.
    client.cookies.clear()
    next_fail_resp = await client.post("/auth/login", json={"email": email, "password": "wrong-password"})
    assert next_fail_resp.status_code == 401


# ---------------------------- lockout key isolation across flows (real Redis) ----------------------------
#
# Regression coverage for a bug where password_reset_confirm_handler and
# account_verification_handler shared login_handler's exact "login_lock:
# email:{email}" Redis key. That meant failures with no bearing on a real
# login attempt, such as a weak new password during reset, or an already-verified
# account being re-submitted for verification, counted towards, and could
# trip, the unrelated login lockout for the same email. Each flow now uses
# its own key namespace (password_reset_confirm_lock / verify_account_lock).

@pytest.mark.asyncio
async def test_repeated_weak_password_reset_confirm_failures_do_not_lock_out_login(client, created_emails):
    email = _unique_email()
    await _signup_verify_login(client, created_emails, email)
    client.cookies.clear()

    reset_token = await _request_password_reset(client, email)
    for _ in range(settings.MAX_FAILED_LOGIN_ATTEMPTS):
        # Too-short new password fails validate_password_strength, which
        # restores the single-use Redis entry so the same token can be
        # retried, letting this loop drive enough failures to have tripped
        # the old shared lockout key.
        resp = await client.post(
            "/auth/password-reset/confirm", json={"token": reset_token, "new_password": "weak"}
        )
        assert resp.status_code == 400

    login_resp = await client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert login_resp.status_code == 200


@pytest.mark.asyncio
async def test_repeated_already_verified_failures_do_not_lock_out_login(client, created_emails):
    email = _unique_email()
    await _signup_verify_login(client, created_emails, email)
    client.cookies.clear()

    for _ in range(settings.MAX_FAILED_LOGIN_ATTEMPTS):
        # A fresh, valid, single-use-registered token for an account that's
        # already verified: verify_token succeeds (real token, real Redis
        # single-use entry) but mark_user_verified fails because is_verified
        # is already True: the "already verified" failure branch.
        token = await account_verification_service.create_verification_token(email)
        await redis_client.set(f"verify:{token}", "1", ex=600)
        resp = await client.post("/auth/verify-account", json={"token": token})
        assert resp.status_code == 400

    login_resp = await client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert login_resp.status_code == 200


# ---------------------------- refresh rotation / reuse detection ----------------------------

@pytest.mark.asyncio
async def test_refresh_token_rotates_and_old_token_is_rejected(client, created_emails):
    email = _unique_email()
    login_resp = await _signup_verify_login(client, created_emails, email)
    old_refresh = login_resp.cookies["refresh_token"]

    refresh_resp = await _refresh_with_cookie(client, old_refresh)
    assert refresh_resp.status_code == 200
    new_refresh = refresh_resp.cookies["refresh_token"]
    assert new_refresh != old_refresh

    reuse_resp = await _refresh_with_cookie(client, old_refresh)
    assert reuse_resp.status_code == 401


@pytest.mark.asyncio
async def test_concurrent_refresh_with_the_same_token_only_one_succeeds(client, created_emails):
    # Regression guard for the refresh-token double-spend race: two requests
    # firing concurrently with the identical still-valid refresh token must
    # not both be able to rotate it into a new pair: claim_jti_for_rotation's
    # atomic Redis SET...NX means only one can ever win, regardless of how
    # the two requests interleave.
    email = _unique_email()
    login_resp = await _signup_verify_login(client, created_emails, email)
    refresh_token = login_resp.cookies["refresh_token"]

    client.cookies.set("refresh_token", refresh_token, domain=_TEST_COOKIE_DOMAIN, path="/auth")
    responses = await asyncio.gather(
        client.post("/auth/refresh/"),
        client.post("/auth/refresh/"),
    )

    statuses = sorted(resp.status_code for resp in responses)
    # Exactly one of the two concurrent requests may win the claim; the
    # other loses the atomic SET...NX and is treated as reuse (401).
    assert statuses == [200, 401]


@pytest.mark.asyncio
async def test_refresh_token_reuse_revokes_all_sessions(client, created_emails):
    email = _unique_email()
    login_resp = await _signup_verify_login(client, created_emails, email)
    device_a_refresh = login_resp.cookies["refresh_token"]

    # A second, independent session/device for the same user.
    second_login = await client.post("/auth/login", json={"email": email, "password": PASSWORD})
    device_b_refresh = second_login.cookies["refresh_token"]

    # Rotate device A forward once (the legitimate use), then replay the
    # original, now-revoked device A token, simulating a stolen refresh
    # token being used after the real client already rotated it.
    await _refresh_with_cookie(client, device_a_refresh)
    reuse_resp = await _refresh_with_cookie(client, device_a_refresh)
    assert reuse_resp.status_code == 401

    # Reuse detection must revoke every active session for the user,
    # including device B's still-otherwise-valid refresh token.
    device_b_resp = await _refresh_with_cookie(client, device_b_refresh)
    assert device_b_resp.status_code == 401


@pytest.mark.asyncio
async def test_refresh_rejects_access_token_type(client, created_emails):
    email = _unique_email()
    login_resp = await _signup_verify_login(client, created_emails, email)
    access_token = login_resp.cookies["access_token"]

    resp = await _refresh_with_cookie(client, access_token)

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
    email = _unique_email()
    await _signup_verify_login(client, created_emails, email)

    expired_payload = {
        "email": email,
        "type": "refresh",
        "jti": uuid.uuid4().hex,
        "exp": datetime.now(UTC) - timedelta(minutes=1),
    }
    expired_token = pyjwt.encode(expired_payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

    resp = await _refresh_with_cookie(client, expired_token)

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
    email = _unique_email()
    login_resp = await _signup_verify_login(client, created_emails, email)
    refresh_token = login_resp.cookies["refresh_token"]

    for _ in range(settings.MAX_FAILED_LOGIN_ATTEMPTS + 2):
        resp = await _refresh_with_cookie(client, refresh_token)
        assert resp.status_code == 200
        refresh_token = resp.cookies["refresh_token"]


# ---------------------------- logout / logout-all ----------------------------

@pytest.mark.asyncio
async def test_refresh_token_cookie_is_scoped_to_auth_path(client, created_emails):
    # Real end-to-end check (real cookie jar, real Set-Cookie parsing) that
    # refresh_token is scoped to /auth, unlike access_token, which stays
    # site-wide since /users/* routes need it too.
    email = _unique_email()
    await _signup_verify_login(client, created_emails, email)

    cookies_by_name = {cookie.name: cookie for cookie in client.cookies.jar}
    assert cookies_by_name["refresh_token"].path == "/auth"
    assert cookies_by_name["access_token"].path == "/"


@pytest.mark.asyncio
async def test_logout_actually_clears_the_scoped_refresh_token_cookie(client, created_emails):
    # Regression guard: logout's delete_cookie call must use the same
    # path="/auth" the cookie was set with, or the browser (real cookie jar
    # here) never actually removes it, it just leaves the real one behind
    # and layers an ignored, differently-scoped tombstone next to it.
    email = _unique_email()
    await _signup_verify_login(client, created_emails, email)
    assert any(cookie.name == "refresh_token" for cookie in client.cookies.jar)

    logout_resp = await client.post("/auth/logout")
    assert logout_resp.status_code == 200

    assert not any(cookie.name == "refresh_token" for cookie in client.cookies.jar)


@pytest.mark.asyncio
async def test_logout_revokes_refresh_token(client, created_emails):
    email = _unique_email()
    login_resp = await _signup_verify_login(client, created_emails, email)
    refresh_token = login_resp.cookies["refresh_token"]

    logout_resp = await client.post("/auth/logout")
    assert logout_resp.status_code == 200

    reuse_resp = await _refresh_with_cookie(client, refresh_token)
    assert reuse_resp.status_code == 401


@pytest.mark.asyncio
async def test_logout_all_revokes_every_device(client, created_emails):
    email = _unique_email()
    login_resp = await _signup_verify_login(client, created_emails, email)
    device_a_refresh = login_resp.cookies["refresh_token"]

    second_login = await client.post("/auth/login", json={"email": email, "password": PASSWORD})
    device_b_refresh = second_login.cookies["refresh_token"]

    logout_all_resp = await client.post("/auth/logout/all")
    assert logout_all_resp.status_code == 200

    a_resp = await _refresh_with_cookie(client, device_a_refresh)
    b_resp = await _refresh_with_cookie(client, device_b_refresh)
    assert a_resp.status_code == 401
    assert b_resp.status_code == 401


# ---------------------------- password reset ----------------------------

async def _request_password_reset(client, email: str) -> str:
    """Mirrors password_reset_service.send_reset_email's Redis single-use
    registration so the test can drive password-reset/confirm without
    depending on the Taskiq email worker being up to deliver the link."""
    from backend.mystic_auth.auth.password_logic.password_service import password_service

    resp = await client.post("/auth/password-reset/request", json={"email": email})
    assert resp.status_code == 200

    token = await password_service.create_reset_token(email)
    await redis_client.set(f"password_reset:{token}", "1", ex=settings.RESET_TOKEN_EXPIRE_MINUTES * 60)
    return token


@pytest.mark.asyncio
async def test_password_reset_revokes_existing_sessions(client, created_emails):
    email = _unique_email()
    login_resp = await _signup_verify_login(client, created_emails, email)
    old_refresh = login_resp.cookies["refresh_token"]

    new_password = "EvenStrongerPass456!"
    reset_token = await _request_password_reset(client, email)

    confirm_resp = await client.post(
        "/auth/password-reset/confirm", json={"token": reset_token, "new_password": new_password}
    )
    assert confirm_resp.status_code == 200

    # The gap finding #2 fixed: a stolen refresh token from before the reset
    # must no longer work afterwards.
    reuse_resp = await _refresh_with_cookie(client, old_refresh)
    assert reuse_resp.status_code == 401

    # New credentials work; old ones don't.
    old_login = await client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert old_login.status_code == 401
    new_login = await client.post("/auth/login", json={"email": email, "password": new_password})
    assert new_login.status_code == 200


@pytest.mark.asyncio
async def test_password_reset_token_is_single_use(client, created_emails):
    email = _unique_email()
    await _signup_verify_login(client, created_emails, email)

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
    email = _unique_email()
    await _signup_verify_login(client, created_emails, email)
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
    # The core TOCTOU race (real Redis, real Postgres): two requests firing
    # concurrently with the same valid token and *different* new passwords
    # must not both succeed: GETDEL's atomicity means only one can ever
    # win the single-use check, regardless of how the DB writes interleave.
    email = _unique_email()
    await _signup_verify_login(client, created_emails, email)
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
    # Exactly one of the two concurrent requests may succeed; the other
    # loses the atomic GETDEL and gets password_reset_confirm_handler's
    # standard "Invalid token or password" failure response.
    assert statuses == [200, 400]

    # Confirm exactly one of the two candidate passwords actually works.
    login_a = await client.post("/auth/login", json={"email": email, "password": "ConcurrentPassA1!"})
    login_b = await client.post("/auth/login", json={"email": email, "password": "ConcurrentPassB2!"})
    assert sorted([login_a.status_code, login_b.status_code]) == [200, 401]


# ---------------------------- rate limiting (real Redis) ----------------------------

@pytest.mark.asyncio
async def test_ip_rate_limit_blocks_after_max_requests_per_window(client, created_emails):
    # Uses oauth2/login/google rather than /auth/login: that endpoint has no
    # account-level lockout side effect, so exactly MAX_REQUESTS_PER_WINDOW
    # requests exercise only the per-IP rate limiter in isolation, in real
    # Redis, instead of tripping login_protection_service's 5-attempt
    # lockout first.
    for _ in range(settings.MAX_REQUESTS_PER_WINDOW):
        resp = await client.get("/auth/oauth2/login/google")
        assert resp.status_code in (302, 307)

    over_limit_resp = await client.get("/auth/oauth2/login/google")
    assert over_limit_resp.status_code == 429


@pytest.mark.asyncio
async def test_signup_account_key_rate_limit_is_tracked_in_real_redis(client, created_emails):
    # Regression guard for finding #8's fix and the account_key_func wiring
    # in auth_routes.py: confirm the per-account signup key is actually
    # incremented in real Redis, not just under a mock.
    email = _unique_email()
    await client.post("/auth/signup", json={"name": "A", "email": email, "password": PASSWORD})
    created_emails.append(email)

    count = await redis_client.get(f"signup:account:{email}")
    assert count is not None
    assert int(count) == 1
