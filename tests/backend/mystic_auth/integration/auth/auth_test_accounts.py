# tests/backend/mystic_auth/integration/auth_test_accounts.py
#
# Shared signup/login/cookie helpers for the auth-flow integration test
# files (test_login_integration.py, test_refresh_token_integration.py,
# test_logout_password_reset_integration.py): all three need a real
# verified account and the same cookie-jar manipulation to simulate
# stale/reused/forged/cross-session tokens.
import uuid

from backend.mystic_auth.auth.verify_account.account_verification_service import (
    account_verification_service,
)
from backend.mystic_auth.redis.client import redis_client

PASSWORD = "StrongPass123!"


def unique_email() -> str:
    return f"inttest-{uuid.uuid4().hex}@example.com"


# conftest.py's `client` fixture uses base_url="https://testserver", a
# dotless hostname, which CPython's http.cookiejar (what httpx's cookie jar
# is built on) normalizes to "testserver.local" internally for matching
# purposes. Cookies set manually here must match that (domain, path, name)
# key exactly, or they land as a second, separate jar entry instead of
# overwriting the real one from a prior response: see
# refresh_with_cookie's docstring below for why that matters. Exported (not
# module-private) since test_refresh_token_integration.py also needs it to
# set up a concurrent-refresh race directly on the client's cookie jar.
TEST_COOKIE_DOMAIN = "testserver.local"


async def refresh_with_cookie(client, refresh_token: str):
    """Calls /auth/refresh/ with an explicit refresh_token cookie value,
    independent of whatever the client's shared cookie jar currently holds,
    needed to simulate stale/reused/forged/cross-session tokens. httpx
    deprecated per-request `cookies=` in favor of setting cookies on the
    client itself, hence setting it here rather than passing `cookies=`.
    Both domain and path must match the real cookie's (see
    TEST_COOKIE_DOMAIN above): the jar keys cookies by (domain, path,
    name), so an inexact match creates a second entry alongside the real one
    instead of overwriting it, which then survives the endpoint's own
    cookie-clearing response untouched."""
    client.cookies.set("refresh_token", refresh_token, domain=TEST_COOKIE_DOMAIN, path="/auth")
    return await client.post("/auth/refresh/")


async def get_me_with_access_token(client, access_token: str):
    """Calls /auth/me with an explicit access_token cookie value, independent
    of whatever the client's shared cookie jar currently holds - the
    access_token counterpart to refresh_with_cookie above, used to simulate
    a second device's still-cached access token after the first device
    revokes it account-wide (logout-all/password-reset/etc)."""
    client.cookies.set("access_token", access_token, domain=TEST_COOKIE_DOMAIN, path="/")
    return await client.get("/auth/me")


async def signup_verify_login(client, created_emails, email: str, password: str = PASSWORD):
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
