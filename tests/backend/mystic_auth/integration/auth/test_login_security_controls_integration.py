# tests/backend/mystic_auth/integration/auth/test_login_security_controls_integration.py
#
# End-to-end coverage for the login timing side-channel, login lockout,
# lockout key isolation across flows, and IP/account rate limiting, against
# the real ASGI app, real PostgreSQL, and real Valkey (see conftest.py). See
# test_login_integration.py for the base signup/verify/login coverage.
# Unlike the mocked unit suite, these exercise real Valkey type/atomicity
# behavior, the class of bug (a Set/Hash key-type collision) that mocks
# can't surface.
import statistics
import time

import pytest

from backend.mystic_auth.auth.password_logic.password_service import (
    password_service,
)
from backend.mystic_auth.auth.verify_account.account_verification_service import (
    account_verification_service,
)
from backend.mystic_auth.core.settings import settings
from backend.mystic_auth.valkey.client import valkey_client

from .auth_test_accounts import PASSWORD, signup_verify_login, unique_email

# ---------------------------- login timing side-channel ----------------------------

async def _median_login_latency(client, email: str, password: str, samples: int = 9) -> float:
    durations = []
    for _ in range(samples):
        # Reset the lockout counter before every sample, otherwise repeated
        # wrong-password attempts against the same email trip
        # MAX_FAILED_LOGIN_ATTEMPTS partway through, and the locked-out
        # responses (which return instantly, before any hash comparison)
        # would corrupt this timing measurement rather than reflect it.
        await valkey_client.delete(f"login_lock:email:{email}")
        start = time.perf_counter()
        await client.post("/auth/login", json={"email": email, "password": password})
        durations.append(time.perf_counter() - start)
        client.cookies.clear()
    return statistics.median(durations)


@pytest.mark.asyncio
async def test_login_timing_does_not_distinguish_nonexistent_from_wrong_password(client, created_emails):
    # Regression guard for the login timing side-channel (real Argon2, real
    # DB; a mocked test can't observe this since it doesn't perform real
    # hashing). Before the fix, "no such account" returned in a fraction of
    # the time "wrong password on a real account" took, since only the
    # latter paid for an Argon2 comparison. Both must now cost about the
    # same.
    email = unique_email()
    await signup_verify_login(client, created_emails, email)
    client.cookies.clear()

    nonexistent_latency = await _median_login_latency(client, unique_email(), "wrong-password")
    wrong_password_latency = await _median_login_latency(client, email, "wrong-password")

    # Generous tolerance to absorb normal jitter: the bug this guards
    # against produces an orders-of-magnitude gap (no hashing vs. real
    # Argon2), so 3x is still a tight bound.
    assert nonexistent_latency < wrong_password_latency * 3
    assert wrong_password_latency < nonexistent_latency * 3


@pytest.mark.asyncio
async def test_login_timing_does_not_distinguish_unverified_from_wrong_password(client, created_emails):
    verified_email = unique_email()
    await signup_verify_login(client, created_emails, verified_email)
    client.cookies.clear()

    unverified_email = unique_email()
    await client.post(
        "/auth/signup", json={"name": "Unverified", "email": unverified_email, "password": PASSWORD}
    )
    created_emails.append(unverified_email)

    unverified_latency = await _median_login_latency(client, unverified_email, "wrong-password")
    wrong_password_latency = await _median_login_latency(client, verified_email, "wrong-password")

    assert unverified_latency < wrong_password_latency * 3
    assert wrong_password_latency < unverified_latency * 3


# ---------------------------- login lockout (real Valkey) ----------------------------

@pytest.mark.asyncio
async def test_login_locks_out_after_max_failed_attempts(client, created_emails):
    email = unique_email()
    await signup_verify_login(client, created_emails, email)
    client.cookies.clear()

    for _attempt in range(settings.MAX_FAILED_LOGIN_ATTEMPTS):
        resp = await client.post("/auth/login", json={"email": email, "password": "wrong-password"})
        assert resp.status_code == 401

    locked_resp = await client.post("/auth/login", json={"email": email, "password": "wrong-password"})
    assert locked_resp.status_code == 429

    # Even the correct password is rejected while locked out.
    still_locked_resp = await client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert still_locked_resp.status_code == 429


@pytest.mark.asyncio
async def test_successful_login_resets_failed_attempt_counter(client, created_emails):
    email = unique_email()
    await signup_verify_login(client, created_emails, email)
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


# ---------------------------- lockout key isolation across flows (real Valkey) ----------------------------
#
# Regression coverage for a bug where password_reset_confirm_handler and
# account_verification_handler shared login_handler's exact "login_lock:
# email:{email}" Valkey key. Failures with no bearing on a real login
# attempt (a weak new password during reset, an already-verified account
# resubmitted for verification) could trip the unrelated login lockout for
# the same email. Each flow now uses its own key namespace
# (password_reset_confirm_lock / verify_account_lock).

@pytest.mark.asyncio
async def test_repeated_weak_password_reset_confirm_failures_do_not_lock_out_login(client, created_emails):
    email = unique_email()
    await signup_verify_login(client, created_emails, email)
    client.cookies.clear()

    resp = await client.post("/auth/password-reset/request", json={"email": email})
    assert resp.status_code == 200
    reset_token = await password_service.create_reset_token(email)
    await valkey_client.set(f"password_reset:{reset_token}", "1", ex=settings.RESET_TOKEN_EXPIRE_MINUTES * 60)

    for attempt in range(settings.MAX_FAILED_LOGIN_ATTEMPTS):
        # Too-short new password fails validate_password_strength, which
        # restores the single-use Valkey entry so the same token can be
        # retried, letting this loop drive enough failures to trip the old
        # shared lockout key.
        resp = await client.post(
            "/auth/password-reset/confirm", json={"token": reset_token, "new_password": "weak"}
        )
        assert resp.status_code == (429 if attempt == settings.MAX_FAILED_LOGIN_ATTEMPTS - 1 else 400)

    login_resp = await client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert login_resp.status_code == 200


@pytest.mark.asyncio
async def test_repeated_already_verified_failures_do_not_lock_out_login(client, created_emails):
    email = unique_email()
    await signup_verify_login(client, created_emails, email)
    client.cookies.clear()

    for attempt in range(settings.MAX_FAILED_LOGIN_ATTEMPTS):
        # A fresh, valid, single-use-registered token for an account that's
        # already verified: verify_token succeeds (real token, real Valkey
        # single-use entry) but mark_user_verified fails because is_verified
        # is already True, the "already verified" failure branch.
        token = await account_verification_service.create_verification_token(email)
        await valkey_client.set(f"verify:{token}", "1", ex=600)
        resp = await client.post("/auth/verify-account", json={"token": token})
        assert resp.status_code == (429 if attempt == settings.MAX_FAILED_LOGIN_ATTEMPTS - 1 else 400)

    login_resp = await client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert login_resp.status_code == 200


# ---------------------------- rate limiting (real Valkey) ----------------------------

@pytest.mark.asyncio
async def test_ip_rate_limit_blocks_after_max_requests_per_window(client, created_emails):
    # Uses oauth2/login/google rather than /auth/login: that endpoint has no
    # account-level lockout side effect, so exactly MAX_REQUESTS_PER_WINDOW
    # requests exercise only the per-IP rate limiter, in real Valkey,
    # instead of tripping login_protection_service's lockout first.
    for _ in range(settings.MAX_REQUESTS_PER_WINDOW):
        resp = await client.get("/auth/oauth2/login/google")
        assert resp.status_code in (302, 307)

    # Rate-limiting this route redirects back to /login (with a
    # ?error=TOO_MANY_ATTEMPTS the frontend translates and displays) rather
    # than a raw JSON 429 body: this is a top-level browser navigation, not
    # an API call with somewhere to render JSON. See
    # rate_limiter_service.rate_limited's redirect_url param.
    over_limit_resp = await client.get("/auth/oauth2/login/google")
    assert over_limit_resp.status_code in (302, 307)
    assert over_limit_resp.headers["location"] == f"{settings.FRONTEND_BASE_URL}/login?error=TOO_MANY_ATTEMPTS"


@pytest.mark.asyncio
async def test_signup_account_key_rate_limit_is_tracked_in_real_valkey(client, created_emails):
    # Regression guard for the account_key_func wiring in auth_routes.py:
    # confirm the per-account signup key is actually incremented in real
    # Valkey, not just under a mock.
    email = unique_email()
    await client.post("/auth/signup", json={"name": "A", "email": email, "password": PASSWORD})
    created_emails.append(email)

    count = await valkey_client.get(f"signup:account:{email}")
    assert count is not None
    assert int(count) == 1
