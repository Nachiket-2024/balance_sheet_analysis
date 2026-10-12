# tests/backend/mystic_auth/integration/audit_log/test_security_audit_log_integration.py
#
# End-to-end coverage for the persistent security audit log
# (audit_log/audit_log_model.py, audit_log/audit_log_repository.py, and the
# /audit/security-log query routes) against the real ASGI app, real
# PostgreSQL, and real Valkey. Security-sensitive auth events (login,
# logout, signup, etc.) must be persisted automatically, and the query API
# itself must be PBAC-gated (security_audit:read).
import uuid
from datetime import UTC, datetime, timedelta

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
async def test_unauthenticated_request_is_rejected(client):
    resp = await client.get("/audit/security-log")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_regular_user_cannot_query_the_global_security_audit_log(client, created_emails):
    email = _unique_email()
    await _create_verified_user(client, created_emails, email, [SELF_SERVICE_POLICY_NAME])

    resp = await client.get("/audit/security-log")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_system_user_can_list_the_global_security_audit_log(client, created_emails):
    system_email = _unique_email("system")
    await _create_system_user(client, created_emails, system_email)

    resp = await client.get("/audit/security-log", params={"limit": 5})
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
    assert len(resp.json()) <= 5


@pytest.mark.asyncio
async def test_regular_user_can_read_their_own_security_log(client, created_emails):
    email = _unique_email()
    await _create_verified_user(client, created_emails, email, [SELF_SERVICE_POLICY_NAME])

    resp = await client.get("/audit/security-log/me")
    assert resp.status_code == 200
    entries = resp.json()
    assert all(e["user_email"] == email for e in entries if e["user_email"] is not None)


@pytest.mark.asyncio
async def test_global_security_log_search_filters_by_user_email(client, created_emails):
    system_email = _unique_email("system")
    await _create_system_user(client, created_emails, system_email)
    target_email = _unique_email("searchtarget")
    # Signup alone (see test_signup_writes_a_signup_audit_entry) already
    # writes a SIGNUP security-log entry for target_email. Ends logged in
    # as target_email, so switch back to the system user afterwards.
    await _create_verified_user(client, created_emails, target_email, [SELF_SERVICE_POLICY_NAME])
    login_resp = await client.post("/auth/login", json={"email": system_email, "password": PASSWORD})
    assert login_resp.status_code == 200

    resp = await client.get("/audit/security-log", params={"search": target_email, "limit": 100})
    assert resp.status_code == 200
    entries = resp.json()
    assert entries
    assert all(e["user_email"] == target_email for e in entries)


@pytest.mark.asyncio
async def test_global_security_log_sort_by_user_email(client, created_emails):
    system_email = _unique_email("system")
    await _create_system_user(client, created_emails, system_email)

    # Two distinct, known-orderable emails sharing a common search prefix so
    # this test's own rows are isolated from other entries in the table.
    prefix = _unique_email("sorttest").split("@")[0]
    email_a = f"{prefix}-aaa@example.com"
    email_b = f"{prefix}-bbb@example.com"
    # Each signup alone writes a SIGNUP security-log entry.
    await _create_verified_user(client, created_emails, email_b, [SELF_SERVICE_POLICY_NAME])
    await _create_verified_user(client, created_emails, email_a, [SELF_SERVICE_POLICY_NAME])

    login_resp = await client.post("/auth/login", json={"email": system_email, "password": PASSWORD})
    assert login_resp.status_code == 200

    resp = await client.get(
        "/audit/security-log",
        params={"search": prefix, "sort_by": "user_email", "sort_dir": "asc", "limit": 100},
    )
    assert resp.status_code == 200
    emails = [e["user_email"] for e in resp.json()]
    assert emails == sorted(emails)
    assert email_a in emails
    assert email_b in emails
    assert emails.index(email_a) < emails.index(email_b)


@pytest.mark.asyncio
async def test_global_security_log_filters_by_event_type_and_success(client, created_emails):
    system_email = _unique_email("system")
    await _create_system_user(client, created_emails, system_email)
    target_email = _unique_email("filtertarget")
    # Ends logged in as target_email.
    await _create_verified_user(client, created_emails, target_email, [SELF_SERVICE_POLICY_NAME])

    # A failed login (wrong password) writes a login_failure/success=false
    # row; a successful one writes login_success/success=true.
    failed_resp = await client.post(
        "/auth/login", json={"email": target_email, "password": "definitely-wrong-password"}
    )
    assert failed_resp.status_code == 401
    success_resp = await client.post("/auth/login", json={"email": target_email, "password": PASSWORD})
    assert success_resp.status_code == 200

    login_resp = await client.post("/auth/login", json={"email": system_email, "password": PASSWORD})
    assert login_resp.status_code == 200

    failure_only = await client.get(
        "/audit/security-log",
        params={"search": target_email, "event_type": "login_failure", "success": False, "limit": 100},
    )
    assert failure_only.status_code == 200
    failure_entries = failure_only.json()
    assert failure_entries
    assert all(e["event_type"] == "login_failure" and e["success"] is False for e in failure_entries)

    success_only = await client.get(
        "/audit/security-log",
        params={"search": target_email, "event_type": "login_success", "success": True, "limit": 100},
    )
    assert success_only.status_code == 200
    success_entries = success_only.json()
    assert success_entries
    assert all(e["event_type"] == "login_success" and e["success"] is True for e in success_entries)


@pytest.mark.asyncio
async def test_global_security_log_filters_by_from_and_to(client, created_emails):
    system_email = _unique_email("system")
    await _create_system_user(client, created_emails, system_email)
    target_email = _unique_email("rangetarget")
    # Signup alone writes a SIGNUP row for target_email, timestamped "now".
    await _create_verified_user(client, created_emails, target_email, [SELF_SERVICE_POLICY_NAME])

    login_resp = await client.post("/auth/login", json={"email": system_email, "password": PASSWORD})
    assert login_resp.status_code == 200

    now = datetime.now(UTC)

    in_range = await client.get(
        "/audit/security-log",
        params={
            "search": target_email,
            "from": (now - timedelta(minutes=5)).isoformat(),
            "to": (now + timedelta(minutes=5)).isoformat(),
            "limit": 100,
        },
    )
    assert in_range.status_code == 200
    in_range_entries = in_range.json()
    assert in_range_entries
    assert all(e["user_email"] == target_email for e in in_range_entries)

    before_row_existed = await client.get(
        "/audit/security-log",
        params={"search": target_email, "to": (now - timedelta(minutes=5)).isoformat(), "limit": 100},
    )
    assert before_row_existed.status_code == 200
    assert before_row_existed.json() == []

    after_row_existed = await client.get(
        "/audit/security-log",
        params={"search": target_email, "from": (now + timedelta(minutes=5)).isoformat(), "limit": 100},
    )
    assert after_row_existed.status_code == 200
    assert after_row_existed.json() == []


@pytest.mark.asyncio
async def test_user_security_log_requires_security_audit_read(client, created_emails):
    """The admin per-user route (UserAccessDialog's "Recent access changes")
    is gated the same as the global list, not self-scoped like /me - a
    caller without security_audit:read must be refused even when asking
    about their own email through this route."""
    email = _unique_email()
    await _create_verified_user(client, created_emails, email, [SELF_SERVICE_POLICY_NAME])

    resp = await client.get(f"/audit/security-log/users/{email}")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_user_security_log_scopes_to_the_path_user_only(client, created_emails):
    system_email = _unique_email("system")
    await _create_system_user(client, created_emails, system_email)
    target_email = _unique_email("usertarget")
    other_email = _unique_email("otheruser")
    # Both signups alone write a SIGNUP row for each email; ends logged in
    # as other_email, so log back in as the system user afterwards.
    await _create_verified_user(client, created_emails, target_email, [SELF_SERVICE_POLICY_NAME])
    await _create_verified_user(client, created_emails, other_email, [SELF_SERVICE_POLICY_NAME])
    login_resp = await client.post("/auth/login", json={"email": system_email, "password": PASSWORD})
    assert login_resp.status_code == 200

    resp = await client.get(f"/audit/security-log/users/{target_email}", params={"limit": 100})
    assert resp.status_code == 200
    entries = resp.json()
    assert entries
    assert all(e["user_email"] == target_email for e in entries)


@pytest.mark.asyncio
async def test_user_security_log_access_change_alias_filters_to_admin_actions_only(client, created_emails):
    """event_type=access_change (UserAccessDialog's "Recent access changes")
    must return only the events that represent an admin changing this
    user's access (policy assign/revoke here), never the account's own
    unrelated auth activity (its own signup row) even though both are on
    the same user_email."""
    system_email = _unique_email("system")
    await _create_system_user(client, created_emails, system_email)
    target_email = _unique_email("changetarget")
    # Signup alone writes a non-access-change SIGNUP row for target_email.
    await _create_verified_user(client, created_emails, target_email, [SELF_SERVICE_POLICY_NAME])
    login_resp = await client.post("/auth/login", json={"email": system_email, "password": PASSWORD})
    assert login_resp.status_code == 200

    assign_resp = await client.post(
        f"/authorization/users/{target_email}/policies",
        json={"policy_name": USER_MANAGEMENT_POLICY_NAME},
    )
    assert assign_resp.status_code == 200

    resp = await client.get(
        f"/audit/security-log/users/{target_email}", params={"event_type": "access_change", "limit": 100}
    )
    assert resp.status_code == 200
    entries = resp.json()
    assert entries
    event_types = {e["event_type"] for e in entries}
    assert event_types == {"policy_assigned"}
    assert "signup" not in event_types


@pytest.mark.asyncio
async def test_login_trend_search_filters_by_user_email(client, created_emails):
    system_email = _unique_email("system")
    await _create_system_user(client, created_emails, system_email)
    target_email = _unique_email("trendtarget")
    # Ends logged in as target_email; the signup+verify flow doesn't itself
    # write a login-shaped event, so log in once to get one success row.
    await _create_verified_user(client, created_emails, target_email, [SELF_SERVICE_POLICY_NAME])
    own_login_resp = await client.post("/auth/login", json={"email": target_email, "password": PASSWORD})
    assert own_login_resp.status_code == 200

    login_resp = await client.post("/auth/login", json={"email": system_email, "password": PASSWORD})
    assert login_resp.status_code == 200

    matching = await client.get("/audit/security-log/login-trend", params={"days": 1, "search": target_email})
    assert matching.status_code == 200
    matching_points = matching.json()
    assert matching_points
    assert sum(p["success"] + p["failure"] for p in matching_points) >= 1

    no_match_email = _unique_email("nomatch")
    non_matching = await client.get(
        "/audit/security-log/login-trend", params={"days": 1, "search": no_match_email}
    )
    assert non_matching.status_code == 200
    non_matching_points = non_matching.json()
    assert non_matching_points
    assert sum(p["success"] + p["failure"] for p in non_matching_points) == 0
