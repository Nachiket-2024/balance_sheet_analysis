# tests/backend/mystic_auth/integration/audit_log/test_security_audit_log_integration.py
#
# End-to-end coverage for the persistent security audit log
# (audit_log/audit_log_model.py, audit_log/audit_log_repository.py, and the
# /audit/security-log query routes) against the real ASGI app, real
# PostgreSQL, and real Valkey. Security-sensitive auth events (login,
# logout, signup, etc.) must be persisted automatically, and the query API
# itself must be PBAC-gated (security_audit:read).
import uuid

import pytest
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


def _unique_email(prefix: str = "inttest") -> str:
    return f"{prefix}-{uuid.uuid4().hex}@example.com"


async def _create_verified_user(client, created_emails, email, policy_names):
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


async def _create_system_user(client, created_emails, email):
    return await _create_verified_user(
        client, created_emails, email,
        [SELF_SERVICE_POLICY_NAME, USER_MANAGEMENT_POLICY_NAME, SYSTEM_SUPERUSER_POLICY_NAME],
    )


@pytest_asyncio.fixture(autouse=True)
async def _cleanup_security_audit_log(created_emails):
    """Security audit rows are append-only and not cascade-deleted with a
    test user, so clean up rows for this test's emails so repeated runs
    don't accumulate unbounded log rows in the shared test database."""
    yield
    if not created_emails:
        return
    async with database.async_session() as session:
        await session.execute(
            text("DELETE FROM security_audit_log WHERE user_email = ANY(:emails)"),
            {"emails": created_emails},
        )
        await session.commit()


# ---------------------------- Automatic logging on real auth routes ----------------------------

@pytest.mark.asyncio
async def test_signup_writes_a_signup_audit_entry(client, created_emails):
    email = _unique_email("signup")
    system_email = _unique_email("system")
    await _create_system_user(client, created_emails, system_email)

    signup_resp = await client.post(
        "/auth/signup", json={"name": "Test User", "email": email, "password": PASSWORD}
    )
    assert signup_resp.status_code == 200
    created_emails.append(email)

    log_resp = await client.get("/audit/security-log", params={"limit": 200})
    assert log_resp.status_code == 200
    entries = log_resp.json()

    matching = [e for e in entries if e["event_type"] == "signup" and e["user_email"] == email]
    assert len(matching) == 1
    assert matching[0]["success"] is True


@pytest.mark.asyncio
async def test_login_writes_success_and_failure_audit_entries(client, created_emails):
    email = _unique_email("login")
    system_email = _unique_email("system")
    await _create_verified_user(client, created_emails, email, [SELF_SERVICE_POLICY_NAME])
    await _create_system_user(client, created_emails, system_email)

    # _create_verified_user already performed one successful login
    bad_login_resp = await client.post("/auth/login", json={"email": email, "password": "wrong-password"})
    assert bad_login_resp.status_code == 401

    await client.post("/auth/login", json={"email": system_email, "password": PASSWORD})
    log_resp = await client.get("/audit/security-log", params={"limit": 200})
    assert log_resp.status_code == 200
    entries = log_resp.json()

    matching = [e for e in entries if e["user_email"] == email]
    event_types = {e["event_type"] for e in matching}
    assert "login_success" in event_types
    assert "login_failure" in event_types


@pytest.mark.asyncio
async def test_policy_assign_and_revoke_write_audit_entries(client, created_emails):
    # Regression guard: assign/remove_policy_from_user used to write no
    # security audit entry at all, unlike every other privileged action
    # (login, logout, account delete/purge/reactivate), so granting or
    # revoking a policy, including system_superuser itself, left no trace
    # in the security log. This exercises the real API routes end-to-end.
    email = _unique_email("policytarget")
    system_email = _unique_email("system")
    await _create_verified_user(client, created_emails, email, [SELF_SERVICE_POLICY_NAME])
    # Logs in as the system user, leaving the shared client's cookie jar
    # authenticated as them for the calls below (same pattern as
    # test_login_writes_success_and_failure_audit_entries above).
    await _create_system_user(client, created_emails, system_email)

    assign_resp = await client.post(
        f"/authorization/users/{email}/policies",
        json={"policy_name": USER_MANAGEMENT_POLICY_NAME},
    )
    assert assign_resp.status_code == 200

    revoke_resp = await client.delete(
        f"/authorization/users/{email}/policies/{USER_MANAGEMENT_POLICY_NAME}",
    )
    assert revoke_resp.status_code == 200

    log_resp = await client.get("/audit/security-log", params={"limit": 200})
    assert log_resp.status_code == 200
    entries = log_resp.json()

    matching = {e["event_type"]: e for e in entries if e["user_email"] == email}
    assert "policy_assigned" in matching
    assert matching["policy_assigned"]["success"] is True
    assert matching["policy_assigned"]["event_metadata"] == {
        "assigned_by": system_email,
        "policy_name": USER_MANAGEMENT_POLICY_NAME,
    }
    assert "policy_revoked" in matching
    assert matching["policy_revoked"]["success"] is True
    assert matching["policy_revoked"]["event_metadata"] == {
        "revoked_by": system_email,
        "policy_name": USER_MANAGEMENT_POLICY_NAME,
    }


@pytest.mark.asyncio
async def test_permission_grant_and_revoke_write_complete_audit_metadata(client, created_emails):
    target_email = _unique_email("permtarget")
    system_email = _unique_email("system")
    await _create_verified_user(client, created_emails, target_email, [SELF_SERVICE_POLICY_NAME])
    await _create_system_user(client, created_emails, system_email)

    grant_resp = await client.post(
        f"/authorization/users/{target_email}/permissions",
        json={"action": "users:deactivate_any", "resource_type": "users"},
    )
    assert grant_resp.status_code == 200

    revoke_resp = await client.delete(
        f"/authorization/users/{target_email}/permissions/users:deactivate_any",
        params={"resource_type": "users"},
    )
    assert revoke_resp.status_code == 200

    log_resp = await client.get("/audit/security-log", params={"limit": 200})
    assert log_resp.status_code == 200
    entries = log_resp.json()
    matching = {e["event_type"]: e for e in entries if e["user_email"] == target_email}

    assert matching["permission_granted"]["success"] is True
    assert matching["permission_granted"]["event_metadata"] == {
        "granted_by": system_email,
        "action": "users:deactivate_any",
        "resource_type": "users",
    }
    assert matching["permission_revoked"]["success"] is True
    assert matching["permission_revoked"]["event_metadata"] == {
        "revoked_by": system_email,
        "action": "users:deactivate_any",
        "resource_type": "users",
    }


@pytest.mark.asyncio
async def test_logout_writes_a_logout_audit_entry(client, created_emails):
    email = _unique_email("logout")
    system_email = _unique_email("system")
    await _create_verified_user(client, created_emails, email, [SELF_SERVICE_POLICY_NAME])
    await _create_system_user(client, created_emails, system_email)

    logout_resp = await client.post("/auth/logout")
    assert logout_resp.status_code == 200

    await client.post("/auth/login", json={"email": system_email, "password": PASSWORD})
    log_resp = await client.get("/audit/security-log", params={"limit": 200})
    assert log_resp.status_code == 200
    entries = log_resp.json()

    matching = [e for e in entries if e["event_type"] == "logout"]
    assert len(matching) >= 1


# ---------------------------- Security audit log query API gating ----------------------------
