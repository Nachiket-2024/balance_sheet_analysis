# tests/backend/mystic_auth/integration/test_audit_log_integration.py
#
# End-to-end coverage for the persistent authorization audit log
# (authorization/models/audit_log_model.py, .../repositories/audit_log_repository.py,
# and the /authorization/audit-log query routes) against the real ASGI app,
# real PostgreSQL, and real Redis. Per claude.md's Remaining PBAC Work item
# #1: "Authorization decisions must be auditable" : every real
# authorize()/require() call (i.e. every hit on a PBAC-protected route)
# must write a row automatically, with no route needing to opt in, and the
# query API itself must be PBAC-gated.
import uuid

import pytest
import pytest_asyncio
from backend.mystic_auth.auth.verify_account.account_verification_service import account_verification_service
from backend.mystic_auth.authorization.policies.default_policies import (
    SELF_SERVICE_POLICY_NAME,
    SYSTEM_SUPERUSER_POLICY_NAME,
    USER_ADMINISTRATION_POLICY_NAME,
)
from backend.mystic_auth.authorization.repositories.policy_repository import policy_repository
from backend.mystic_auth.database.connection import database
from backend.mystic_auth.redis.client import redis_client
from backend.mystic_auth.user_crud.user_crud_collector import user_crud
from sqlalchemy import text

PASSWORD = "StrongPass123!"


def _unique_email(prefix: str = "inttest") -> str:
    return f"{prefix}-{uuid.uuid4().hex}@example.com"


async def _create_verified_user(client, created_emails, email, policy_names):
    signup_resp = await client.post(
        "/auth/signup", json={"name": "Test User", "email": email, "password": PASSWORD}
    )
    assert signup_resp.status_code == 200
    created_emails.append(email)

    token = await account_verification_service.create_verification_token(email)
    await redis_client.set(f"verify:{token}", "1", ex=600)
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


async def _create_system_user(client, created_emails, email):
    return await _create_verified_user(
        client, created_emails, email,
        [SELF_SERVICE_POLICY_NAME, USER_ADMINISTRATION_POLICY_NAME, SYSTEM_SUPERUSER_POLICY_NAME],
    )


@pytest_asyncio.fixture(autouse=True)
async def _cleanup_audit_log(created_emails):
    """Every real authorize() call in these tests writes a permanent audit
    row (by design : audit history is append-only, never cascade-deleted
    when a test user is torn down). Clean up rows for this test's emails
    specifically so repeated runs don't accumulate unbounded log rows in
    the shared test database."""
    yield
    if not created_emails:
        return
    async with database.async_session() as session:
        await session.execute(
            text("DELETE FROM authorization_audit_log WHERE user_email = ANY(:emails)"),
            {"emails": created_emails},
        )
        await session.commit()


# ---------------------------- Automatic logging on real protected routes ----------------------------

@pytest.mark.asyncio
async def test_a_successful_protected_action_is_logged_as_allowed(client, created_emails):
    admin_email = _unique_email("admin")
    system_email = _unique_email("system")
    await _create_verified_user(client, created_emails, admin_email, [SELF_SERVICE_POLICY_NAME, USER_ADMINISTRATION_POLICY_NAME])
    await _create_system_user(client, created_emails, system_email)

    login_resp = await client.post("/auth/login", json={"email": admin_email, "password": PASSWORD})
    assert login_resp.status_code == 200
    list_resp = await client.get("/users/")
    assert list_resp.status_code == 200

    # Query the audit log as the system user
    await client.post("/auth/login", json={"email": system_email, "password": PASSWORD})
    log_resp = await client.get(f"/authorization/audit-log/users/{admin_email}")
    assert log_resp.status_code == 200
    entries = log_resp.json()

    matching = [e for e in entries if e["action"] == "users:list_all" and e["resource_type"] == "users"]
    assert len(matching) >= 1
    assert matching[0]["allowed"] is True
    assert "user_administration" in matching[0]["granting_policy_names"]


@pytest.mark.asyncio
async def test_a_denied_protected_action_is_logged_as_denied(client, created_emails):
    plain_email = _unique_email("plain")
    system_email = _unique_email("system")
    await _create_verified_user(client, created_emails, plain_email, [SELF_SERVICE_POLICY_NAME])
    await _create_system_user(client, created_emails, system_email)

    login_resp = await client.post("/auth/login", json={"email": plain_email, "password": PASSWORD})
    assert login_resp.status_code == 200
    denied_resp = await client.get("/users/")
    assert denied_resp.status_code == 403

    await client.post("/auth/login", json={"email": system_email, "password": PASSWORD})
    log_resp = await client.get(f"/authorization/audit-log/users/{plain_email}")
    assert log_resp.status_code == 200
    entries = log_resp.json()

    matching = [e for e in entries if e["action"] == "users:list_all"]
    assert len(matching) >= 1
    assert matching[0]["allowed"] is False
    assert matching[0]["granting_policy_names"] == []


@pytest.mark.asyncio
async def test_inspection_endpoint_does_not_pollute_the_audit_log(client, created_emails):
    # authorization-check calls authorize_detailed directly (a hypothetical
    # "what would happen if" query) : it must never itself write an audit
    # entry, only the real authorize()/require() calls that gate actual
    # routes do.
    target_email = _unique_email("target")
    system_email = _unique_email("system")
    await _create_verified_user(client, created_emails, target_email, [SELF_SERVICE_POLICY_NAME])
    await _create_system_user(client, created_emails, system_email)

    check_resp = await client.post(
        f"/authorization/users/{target_email}/authorization-check",
        json={"action": "users:purge", "resource_type": "users"},
    )
    assert check_resp.status_code == 200

    log_resp = await client.get(f"/authorization/audit-log/users/{target_email}")
    assert log_resp.status_code == 200
    entries = log_resp.json()

    assert all(e["action"] != "users:purge" for e in entries)


# ---------------------------- Audit log query API gating ----------------------------

@pytest.mark.asyncio
async def test_unauthenticated_request_is_rejected(client):
    resp = await client.get("/authorization/audit-log")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_regular_user_cannot_query_the_audit_log(client, created_emails):
    email = _unique_email()
    await _create_verified_user(client, created_emails, email, [SELF_SERVICE_POLICY_NAME])

    resp = await client.get("/authorization/audit-log")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_system_user_can_list_the_global_audit_log(client, created_emails):
    system_email = _unique_email("system")
    await _create_system_user(client, created_emails, system_email)

    resp = await client.get("/authorization/audit-log", params={"limit": 5})
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
    assert len(resp.json()) <= 5


@pytest.mark.asyncio
async def test_audit_log_for_unknown_user_returns_404(client, created_emails):
    system_email = _unique_email("system")
    await _create_system_user(client, created_emails, system_email)

    resp = await client.get(f"/authorization/audit-log/users/{_unique_email('nobody')}")
    assert resp.status_code == 404
