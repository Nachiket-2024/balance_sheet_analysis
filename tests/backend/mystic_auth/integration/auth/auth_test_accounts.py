# tests/backend/mystic_auth/integration/auth/auth_test_accounts.py
#
# Shared signup/login/cookie helpers for the auth-flow integration tests:
# they all need a real verified account and the same cookie-jar
# manipulation to simulate stale/reused/forged/cross-session tokens.
import uuid

from backend.mystic_auth.auth.verify_account.account_verification_service import (
    account_verification_service,
)
from backend.mystic_auth.valkey.client import valkey_client

PASSWORD = "StrongPass123!"


def unique_email() -> str:
    return f"inttest-{uuid.uuid4().hex}@example.com"


# conftest.py's `client` fixture uses base_url="https://testserver", a
# dotless hostname that CPython's http.cookiejar (what httpx's jar is built
# on) normalizes to "testserver.local". Cookies set manually here must match
# that (domain, path, name) key exactly, or they land as a second jar entry
# instead of overwriting the real one (see refresh_with_cookie below).
# Exported since test_refresh_token_integration.py also needs it to set up
# a concurrent-refresh race directly on the client's cookie jar.
TEST_COOKIE_DOMAIN = "testserver.local"


async def refresh_with_cookie(client, refresh_token: str):
    """Calls /auth/refresh/ with an explicit refresh_token cookie value,
    independent of the client's shared jar, to simulate
    stale/reused/forged/cross-session tokens. Sets the cookie on the client
    rather than passing `cookies=`, since httpx deprecated the latter. Domain
    and path must match the real cookie's (see TEST_COOKIE_DOMAIN above): an
    inexact match creates a second jar entry instead of overwriting the
    real one, which then survives the endpoint's own cookie-clearing
    response untouched."""
    client.cookies.set("refresh_token", refresh_token, domain=TEST_COOKIE_DOMAIN, path="/auth")
    return await client.post("/auth/refresh/")


async def get_me_with_access_token(client, access_token: str):
    """Calls /auth/me with an explicit access_token cookie value, independent
    of the client's shared jar. The access_token counterpart to
    refresh_with_cookie above, used to simulate a second device's still-
    cached access token after the first device revokes it account-wide
    (logout-all, password reset, etc)."""
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

    # Verify via a real single-use Valkey-backed token, the same way
    # account_verification_service.send_verification_email would, without
    # depending on the email worker actually being up.
    token = await account_verification_service.create_verification_token(email)
    await valkey_client.set(f"verify:{token}", "1", ex=600)
    verify_resp = await client.post("/auth/verify-account", json={"token": token})
    assert verify_resp.status_code == 200

    login_resp = await client.post("/auth/login", json={"email": email, "password": password})
    assert login_resp.status_code == 200
    return login_resp
