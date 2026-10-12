# tests/backend/mystic_auth/integration/auth/test_logout_integration.py
#
# End-to-end logout/logout-all coverage against the real ASGI app, real
# PostgreSQL, and real Valkey (see conftest.py).
import pytest

from backend.mystic_auth.valkey.client import valkey_client

from .auth_test_accounts import (
    PASSWORD,
    get_me_with_access_token,
    refresh_with_cookie,
    signup_verify_login,
    unique_email,
)

# ---------------------------- logout / logout-all ----------------------------

@pytest.mark.asyncio
async def test_logout_actually_clears_the_scoped_refresh_token_cookie(client, created_emails):
    # Regression guard: logout's delete_cookie call must use the same
    # path="/auth" the cookie was set with, or the browser (real cookie jar
    # here) never removes it: it just leaves the real one behind and layers
    # an ignored, differently-scoped tombstone next to it.
    email = unique_email()
    await signup_verify_login(client, created_emails, email)
    assert any(cookie.name == "refresh_token" for cookie in client.cookies.jar)

    logout_resp = await client.post("/auth/logout")
    assert logout_resp.status_code == 200

    assert not any(cookie.name == "refresh_token" for cookie in client.cookies.jar)


@pytest.mark.asyncio
async def test_logout_revokes_refresh_token(client, created_emails):
    email = unique_email()
    login_resp = await signup_verify_login(client, created_emails, email)
    refresh_token = login_resp.cookies["refresh_token"]

    logout_resp = await client.post("/auth/logout")
    assert logout_resp.status_code == 200

    reuse_resp = await refresh_with_cookie(client, refresh_token)
    assert reuse_resp.status_code == 401


@pytest.mark.asyncio
async def test_logout_all_revokes_every_device(client, created_emails):
    email = unique_email()
    login_resp = await signup_verify_login(client, created_emails, email)
    device_a_refresh = login_resp.cookies["refresh_token"]

    second_login = await client.post("/auth/login", json={"email": email, "password": PASSWORD})
    device_b_refresh = second_login.cookies["refresh_token"]

    logout_all_resp = await client.post("/auth/logout/all")
    assert logout_all_resp.status_code == 200

    a_resp = await refresh_with_cookie(client, device_a_refresh)
    b_resp = await refresh_with_cookie(client, device_b_refresh)
    assert a_resp.status_code == 401
    assert b_resp.status_code == 401


@pytest.mark.asyncio
async def test_logout_all_immediately_invalidates_already_issued_access_tokens(client, created_emails):
    """Regression guard: logout-all used to only revoke each device's
    refresh token, leaving its still-valid access token usable for up to
    ACCESS_TOKEN_EXPIRE_MINUTES: a device stayed logged in until it next
    tried to refresh, not "immediately" as documented. Confirms
    revoke_all_tokens_for_user's account_ver bump kills a still-unexpired
    access token from a different device right away."""
    email = unique_email()
    login_resp = await signup_verify_login(client, created_emails, email)
    device_a_access = login_resp.cookies["access_token"]

    second_login = await client.post("/auth/login", json={"email": email, "password": PASSWORD})
    device_b_access = second_login.cookies["access_token"]

    # Sanity check: both access tokens work before logout-all.
    assert (await get_me_with_access_token(client, device_a_access)).status_code == 200
    assert (await get_me_with_access_token(client, device_b_access)).status_code == 200

    logout_all_resp = await client.post("/auth/logout/all")
    assert logout_all_resp.status_code == 200

    a_me_resp = await get_me_with_access_token(client, device_a_access)
    b_me_resp = await get_me_with_access_token(client, device_b_access)
    assert a_me_resp.status_code == 401
    assert b_me_resp.status_code == 401

    # A token minted after the revoke (e.g. logging back in) must still
    # work. Validity is an integer version comparison (account_ver), not
    # time-based, so this needs no delay to avoid same-second ambiguity.
    fresh_login = await client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert fresh_login.status_code == 200
    fresh_access = fresh_login.cookies["access_token"]
    assert (await get_me_with_access_token(client, fresh_access)).status_code == 200


@pytest.mark.asyncio
async def test_logout_all_survives_valkey_flush(client, created_emails):
    """Revocation authority is durable; cache loss must not resurrect JWTs."""
    email = unique_email()
    login_resp = await signup_verify_login(client, created_emails, email)
    old_access = login_resp.cookies["access_token"]

    assert (await get_me_with_access_token(client, old_access)).status_code == 200
    assert (await client.post("/auth/logout/all")).status_code == 200
    await valkey_client.flushall()

    assert (await get_me_with_access_token(client, old_access)).status_code == 401
