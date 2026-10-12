# tests/backend/mystic_auth/integration/auth/test_signup_verify_concurrency_integration.py
#
# Regression guard for an intermittent verify-account failure reported
# during earlier production-audit work (see concerns.md): chaining
# signup -> create a verification token -> immediately verify it, for many
# accounts in quick succession, was once observed to occasionally reject a
# token as "Invalid, expired, or already used" even though the token had
# just been issued and nothing else writes to the "verify:*" Valkey
# keyspace. Two rounds of focused Valkey-level tracing (valkey-cli MONITOR,
# sequential and concurrent, well over 1000 chains total) never reproduced
# it, so no fix was made. This test exists so that if the underlying
# condition recurs, CI catches it instead of relying on another manual
# investigation.
import asyncio

import pytest
from sqlalchemy import text

from backend.mystic_auth.database.connection import database

from .auth_test_accounts import PASSWORD, unique_email


async def _signup_and_verify(client, created_emails) -> bool:
    """One full chain against the real ASGI app and real Valkey: signup
    (which sends its own verification email/token internally), then
    immediately verify with that same token. Returns True if verification
    succeeded."""
    email = unique_email()
    signup_resp = await client.post(
        "/auth/signup", json={"name": "Race Test", "email": email, "password": PASSWORD}
    )
    if signup_resp.status_code != 200:
        return False
    created_emails.append(email)

    from backend.mystic_auth.auth.verify_account.account_verification_service import (
        account_verification_service,
    )
    from backend.mystic_auth.valkey.client import valkey_client

    # Mirrors signup_verify_login's approach in auth_test_accounts.py: mint
    # a real single-use token the same way the app does internally, rather
    # than depending on the email worker, so this test controls exactly how
    # many chains fire and how quickly.
    token = await account_verification_service.create_verification_token(email)
    await valkey_client.set(f"verify:{token}", "1", ex=600)

    verify_resp = await client.post("/auth/verify-account", json={"token": token})
    return verify_resp.status_code == 200


@pytest.mark.asyncio
async def test_sequential_signup_verify_chains_never_reject_a_fresh_token(client, created_emails):
    failures = 0
    for _ in range(50):
        if not await _signup_and_verify(client, created_emails):
            failures += 1
    assert failures == 0


@pytest.mark.asyncio
async def test_concurrent_signup_verify_chains_never_reject_a_fresh_token(client, created_emails):
    # Each chain uses its own email/token, so there is no legitimate reason
    # for any of these to fail: unlike
    # test_concurrent_refresh_with_the_same_token_only_one_succeeds
    # (test_refresh_token_integration.py), nothing here intentionally
    # contends over a shared key.
    results = await asyncio.gather(
        *(_signup_and_verify(client, created_emails) for _ in range(30))
    )
    assert all(results)


@pytest.mark.asyncio
async def test_concurrent_identical_signups_create_exactly_one_user(client, created_emails):
    # signup_service's check-then-insert (get_by_email, then create) has no
    # locking between the two steps; the users.email unique constraint is
    # what actually stops a duplicate row under real concurrency.
    email = unique_email()
    created_emails.append(email)

    responses = await asyncio.gather(
        *(
            client.post("/auth/signup", json={"name": "Race Test", "email": email, "password": PASSWORD})
            for _ in range(10)
        )
    )
    # Always 200 regardless of outcome (anti-enumeration), so the row count
    # below is what actually proves no duplicate landed.
    assert all(resp.status_code == 200 for resp in responses)

    async with database.async_session() as session:
        result = await session.execute(text("SELECT count(*) FROM users WHERE email = :email"), {"email": email})
        assert result.scalar_one() == 1
