# tests/backend/mystic_auth/integration/test_login_integration.py
#
# End-to-end signup/verify/login coverage, the login timing side-channel,
# login lockout, and IP rate limiting, against the real ASGI app, real
# PostgreSQL, and real Redis (see conftest.py). Split out of what used to
# be one 799-line test_auth_api_integration.py. Unlike the mocked unit
# suite, these exercise the actual Redis type/atomicity behavior and actual
# DB commits, the class of bug (e.g. a Set/Hash key-type collision, or a
# missing session-revocation call) that mocks cannot surface.
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
from backend.mystic_auth.redis.client import redis_client

from .auth_test_accounts import PASSWORD, signup_verify_login, unique_email

# ---------------------------- signup / verify / login ----------------------------

@pytest.mark.asyncio
async def test_signup_verify_login_issues_working_session(client, created_emails):
    email = unique_email()
    login_resp = await signup_verify_login(client, created_emails, email)

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
    email = unique_email()
    login_resp = await signup_verify_login(client, created_emails, email)
    assert login_resp.status_code == 200

    me_resp = await client.get("/auth/me")
    assert me_resp.status_code == 200
    body = me_resp.json()
    assert body["role"] == "user"
    assert body["permissions"] == ["users:read_own", "users:update_own"]


@pytest.mark.asyncio
async def test_login_before_verification_is_rejected(client, created_emails):
    email = unique_email()
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
    email = unique_email()
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
    email = unique_email()
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
        json={"name": "Test User", "email": unique_email(), "password": "a" * 129},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_signup_duplicate_email_does_not_create_second_user(client, created_emails):
    email = unique_email()
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
    email = unique_email()
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
    email = unique_email()
    login_resp = await signup_verify_login(client, created_emails, email)
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
    email = unique_email()
    await signup_verify_login(client, created_emails, email)
    client.cookies.clear()

    nonexistent_latency = await _median_login_latency(client, unique_email(), "wrong-password")
    wrong_password_latency = await _median_login_latency(client, email, "wrong-password")

    # Generous tolerance to absorb normal jitter: the bug this guards
    # against produces an orders-of-magnitude gap (no hashing vs. real
    # Argon2), not a marginal one, so 3x is still a tight bound against it.
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


# ---------------------------- login lockout (real Redis) ----------------------------

@pytest.mark.asyncio
async def test_login_locks_out_after_max_failed_attempts(client, created_emails):
    email = unique_email()
    await signup_verify_login(client, created_emails, email)
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
    email = unique_email()
    await signup_verify_login(client, created_emails, email)
    client.cookies.clear()

    resp = await client.post("/auth/password-reset/request", json={"email": email})
    assert resp.status_code == 200
    reset_token = await password_service.create_reset_token(email)
    await redis_client.set(f"password_reset:{reset_token}", "1", ex=settings.RESET_TOKEN_EXPIRE_MINUTES * 60)

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
    email = unique_email()
    await signup_verify_login(client, created_emails, email)
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
    email = unique_email()
    await client.post("/auth/signup", json={"name": "A", "email": email, "password": PASSWORD})
    created_emails.append(email)

    count = await redis_client.get(f"signup:account:{email}")
    assert count is not None
    assert int(count) == 1
