# tests/backend/mystic_auth/integration/audit_log/audit_log_test_accounts.py
#
# Real signed-up, verified, policy-holding test accounts and the eventual-
# consistency polling helper, shared by the audit log integration tests.
# Mirrors the shared-account-helpers pattern in
# tests/.../user_crud/user_test_accounts.py.
import asyncio
import uuid

import pytest_asyncio
from sqlalchemy import text

from backend.mystic_auth.auth.verify_account.account_verification_service import (
    account_verification_service,
)
from backend.mystic_auth.authorization.policies.default_policies import (
    SELF_SERVICE_POLICY_NAME,
    SYSTEM_SUPERUSER_POLICY_NAME,
    USER_MANAGEMENT_POLICY_NAME,
)
from backend.mystic_auth.authorization.repositories.policy_repository import (
    policy_repository,
)
from backend.mystic_auth.database.connection import database
from backend.mystic_auth.user.user_crud_collector import user_crud
from backend.mystic_auth.valkey.client import valkey_client

PASSWORD = "StrongPass123!"


def unique_email(prefix: str = "inttest") -> str:
    return f"{prefix}-{uuid.uuid4().hex}@example.com"


async def poll_for_entries(fetch, predicate, timeout_seconds: float = 30.0, interval: float = 0.2):
    """Audit rows are written by a background Procrastinate worker (see
    authorization_audit_logger.log_decision), not inline on the request that
    triggered them, so they aren't guaranteed to have landed by the time the
    next request runs. `fetch` is an async callable returning the entries
    list; `predicate` decides whether it already has what the test is
    waiting for. Polls up to `timeout_seconds` rather than assuming instant
    visibility (flaky) or a fixed sleep (slow, still flaky under load).

    Named `timeout_seconds`, not `timeout`, because ruff's ASYNC109 flags a
    bare `timeout` param as looking like `asyncio.timeout()`, which raises
    on expiry. This function instead returns whatever was found when time
    runs out.
    """
    deadline = asyncio.get_event_loop().time() + timeout_seconds
    entries = await fetch()
    while not predicate(entries):
        if asyncio.get_event_loop().time() >= deadline:
            return entries
        await asyncio.sleep(interval)
        entries = await fetch()
    return entries


async def create_verified_user(client, created_emails, email, policy_names):
    signup_resp = await client.post(
        "/auth/signup", json={"name": "Test User", "email": email, "password": PASSWORD}
    )
    assert signup_resp.status_code == 200
    created_emails.append(email)

    token = await account_verification_service.create_verification_token(email)
    await valkey_client.set(f"verify:{token}", "1", ex=600)
    verify_resp = await client.post("/auth/verify-account", json={"token": token})
    assert verify_resp.status_code == 200

    async with database.async_session() as session:
        user = await user_crud.get_by_email(email, session)
        for policy_name in policy_names:
            policy = await policy_repository.get_by_name(policy_name, session)
            await policy_repository.assign_policy_to_user(
                user_id=user.id, policy_id=policy.id, db=session, assigned_by="test"
            )

    login_resp = await client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert login_resp.status_code == 200
    return login_resp


async def create_system_user(client, created_emails, email):
    return await create_verified_user(
        client, created_emails, email,
        [SELF_SERVICE_POLICY_NAME, USER_MANAGEMENT_POLICY_NAME, SYSTEM_SUPERUSER_POLICY_NAME],
    )


@pytest_asyncio.fixture(autouse=True)
async def _cleanup_audit_log(created_emails):
    """Every real authorize() call writes a permanent audit row (audit
    history is append-only, never cascade-deleted with the user). Clean up
    rows for this test's emails so repeated runs don't accumulate unbounded
    log rows."""
    yield
    if not created_emails:
        return
    async with database.async_session() as session:
        await session.execute(
            text("DELETE FROM authorization_audit_log WHERE user_email = ANY(:emails)"),
            {"emails": created_emails},
        )
        await session.commit()
