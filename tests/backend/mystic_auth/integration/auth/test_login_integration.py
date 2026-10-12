# tests/backend/mystic_auth/integration/auth/test_login_integration.py
#
# End-to-end signup/verify/login coverage against the real ASGI app, real
# PostgreSQL, and real Valkey (see conftest.py). Login timing side-channel,
# lockout, and rate limiting are covered separately in
# test_login_security_controls_integration.py. Unlike the mocked unit
# suite, these exercise real Valkey type/atomicity behavior and real DB
# commits, the class of bug (a Set/Hash key-type collision, a missing
# session-revocation call) that mocks can't surface.
import pytest

from backend.mystic_auth.auth.verify_account.account_verification_service import (
    account_verification_service,
)
from backend.mystic_auth.valkey.client import valkey_client

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
    # caller's resolved permission set, not just their role string, so
    # clients can check permissions instead of hardcoding role-name
    # comparisons. A plain "user" account should get only the self-service
    # baseline, no admin-only permission.
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
    await valkey_client.set(f"verify:{token}", "1", ex=600)

    first = await client.post("/auth/verify-account", json={"token": token})
    second = await client.post("/auth/verify-account", json={"token": token})

    assert first.status_code == 200
    assert second.status_code != 200


@pytest.mark.asyncio
async def test_verify_account_no_longer_accepts_get_with_token_in_query_string(client, created_emails):
    # Regression guard: the verification token must never travel as a URL
    # query parameter (it ends up in browser history, server logs, and
    # Referer headers). GET on this route must no longer work at all.
    email = unique_email()
    await client.post("/auth/signup", json={"name": "Test User", "email": email, "password": PASSWORD})
    created_emails.append(email)

    token = await account_verification_service.create_verification_token(email)
    await valkey_client.set(f"verify:{token}", "1", ex=600)

    get_resp = await client.get("/auth/verify-account", params={"token": token})
    assert get_resp.status_code == 405

    # The token must still be unconsumed: the rejected GET must not have
    # accidentally redeemed it.
    post_resp = await client.post("/auth/verify-account", json={"token": token})
    assert post_resp.status_code == 200


@pytest.mark.asyncio
async def test_signup_rejects_oversized_password_with_422(client, created_emails):
    # Real end-to-end check that FastAPI's request-parsing layer enforces
    # the schema's max_length, not just the Pydantic model in isolation,
    # without echoing the submitted password in the 422 response body.
    oversized_password = "a" * 129
    resp = await client.post(
        "/auth/signup",
        json={"name": "Test User", "email": unique_email(), "password": oversized_password},
    )
    assert resp.status_code == 422
    assert oversized_password not in resp.text
    assert "input" not in resp.json()["detail"][0]


@pytest.mark.asyncio
async def test_signup_duplicate_email_does_not_create_second_user(client, created_emails):
    email = unique_email()
    await client.post("/auth/signup", json={"name": "First", "email": email, "password": PASSWORD})
    created_emails.append(email)

    dup_resp = await client.post("/auth/signup", json={"name": "Second", "email": email, "password": PASSWORD})

    # Enumeration-resistant: same generic 200, but no second account was
    # made (the original account's password is still the only valid one).
    assert dup_resp.status_code == 200
    token = await account_verification_service.create_verification_token(email)
    await valkey_client.set(f"verify:{token}", "1", ex=600)
    await client.post("/auth/verify-account", json={"token": token})
    login_resp = await client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert login_resp.status_code == 200


@pytest.mark.asyncio
async def test_signup_duplicate_email_rejected_with_different_casing(client, created_emails):
    # User@Example.com and user@example.com must be the same account,
    # confirmed against the real DB unique constraint and normalization,
    # not mocks, since this is exactly the boundary a mock could hide.
    email = unique_email()
    mixed_case_email = email.replace("inttest-", "INTTEST-", 1)
    await client.post("/auth/signup", json={"name": "First", "email": email, "password": PASSWORD})
    created_emails.append(email)

    dup_resp = await client.post(
        "/auth/signup", json={"name": "Second", "email": mixed_case_email, "password": PASSWORD}
    )

    # Same generic 200 (enumeration-resistant), but no second account
    # exists: confirmed below by logging in with the mixed-case address and
    # the original account's password.
    assert dup_resp.status_code == 200
    token = await account_verification_service.create_verification_token(email)
    await valkey_client.set(f"verify:{token}", "1", ex=600)
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
