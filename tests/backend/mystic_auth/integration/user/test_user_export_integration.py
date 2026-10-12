# tests/backend/mystic_auth/integration/user/test_user_export_integration.py
#
# End-to-end coverage for GET /users/export (CSV export, backing the Users
# page's "Export CSV" button). Uses the same permission (users:list_all)
# and account-setup helpers as test_user_list_and_update_integration.py.
import csv
import io
import uuid

import pytest

from backend.mystic_auth.auth.verify_account.account_verification_service import (
    account_verification_service,
)
from backend.mystic_auth.authorization.policies.default_policies import (
    SELF_SERVICE_POLICY_NAME,
)
from backend.mystic_auth.core.settings import settings
from backend.mystic_auth.valkey.client import valkey_client

from .user_test_accounts import (
    assign_policies,
    create_admin,
    create_verified_user,
    unique_email,
)

PASSWORD = "StrongPass123!"


@pytest.mark.asyncio
async def test_unauthenticated_export_request_is_rejected(client):
    resp = await client.get("/users/export")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_regular_user_cannot_export_users(client, created_emails):
    email = unique_email("plain")
    await create_verified_user(client, created_emails, email)

    resp = await client.get("/users/export")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_can_export_users_as_csv(client, created_emails):
    admin_email = unique_email("admin")
    await create_admin(client, created_emails, admin_email)
    target_email = unique_email("exporttarget")
    await create_verified_user(client, created_emails, target_email)

    await client.post("/auth/login", json={"email": admin_email, "password": PASSWORD})

    resp = await client.get("/users/export", params={"search": target_email.split("@")[0]})

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    assert "attachment; filename=" in resp.headers["content-disposition"]

    rows = list(csv.reader(io.StringIO(resp.text)))
    header, *data_rows = rows
    assert header == ["id", "name", "email", "role", "is_verified", "is_active", "status", "created_at"]
    emails_in_export = [row[2] for row in data_rows]
    assert target_email in emails_in_export
    # Only the search-matched row, not every user in the table.
    assert len(data_rows) == 1


@pytest.mark.asyncio
async def test_export_respects_status_filter_and_marks_deleted_users(client, created_emails):
    admin_email = unique_email("admin")
    await create_admin(client, created_emails, admin_email)
    deleted_email = unique_email("softdeleted")
    await create_verified_user(client, created_emails, deleted_email)

    await client.post("/auth/login", json={"email": admin_email, "password": PASSWORD})
    delete_resp = await client.delete(f"/users/{deleted_email}")
    assert delete_resp.status_code == 200

    deleted_only = await client.get(
        "/users/export", params={"status": "deleted", "search": deleted_email.split("@")[0]}
    )
    rows = list(csv.reader(io.StringIO(deleted_only.text)))
    _, *data_rows = rows
    assert len(data_rows) == 1
    status_col_index = rows[0].index("status")
    assert data_rows[0][status_col_index] == "deleted"

    active_only = await client.get(
        "/users/export", params={"status": "active", "search": deleted_email.split("@")[0]}
    )
    _, *active_rows = list(csv.reader(io.StringIO(active_only.text)))
    assert active_rows == []


@pytest.mark.asyncio
async def test_export_neutralizes_csv_formula_injection_in_name(client, created_emails):
    """`name` is free-form user input with no charset restriction. If it
    starts with a formula-trigger character, the export must prefix it
    with a leading `'`, or opening it in Excel/Sheets/LibreOffice would run
    it as a formula instead of showing it as text (OWASP CSV Injection)."""
    admin_email = unique_email("admin")
    await create_admin(client, created_emails, admin_email)

    payload_name = "=cmd|'/c calc'!A1"
    target_email = unique_email("csvpayload")
    signup_resp = await client.post(
        "/auth/signup", json={"name": payload_name, "email": target_email, "password": PASSWORD}
    )
    assert signup_resp.status_code == 200
    created_emails.append(target_email)
    token = await account_verification_service.create_verification_token(target_email)
    await valkey_client.set(f"verify:{token}", "1", ex=600)
    verify_resp = await client.post("/auth/verify-account", json={"token": token})
    assert verify_resp.status_code == 200
    await assign_policies(target_email, [SELF_SERVICE_POLICY_NAME])

    await client.post("/auth/login", json={"email": admin_email, "password": PASSWORD})
    resp = await client.get("/users/export", params={"search": target_email.split("@")[0]})

    assert resp.status_code == 200
    rows = list(csv.reader(io.StringIO(resp.text)))
    header, *data_rows = rows
    name_col_index = header.index("name")
    assert len(data_rows) == 1
    assert data_rows[0][name_col_index] == f"'{payload_name}"


@pytest.mark.asyncio
async def test_export_neutralizes_csv_formula_injection_in_email(client, created_emails):
    """EmailStr's RFC 5322 local-part allows a leading "=", "+",
    "-", or "@" (unlike name, there's no app-level charset restriction
    stopping it either), so a self-registered account can land a formula
    trigger in the email column too. Must get the same `_csv_safe`
    treatment as name, or opening the export in Excel/Sheets/LibreOffice
    runs it as a live formula (OWASP CSV Injection)."""
    admin_email = unique_email("admin")
    await create_admin(client, created_emails, admin_email)

    # Still unique per run (uuid in the local-part after the trigger char)
    # without going through unique_email(), whose fixed prefix would land
    # after the "=" and defeat the point of this test.
    unique_part = uuid.uuid4().hex
    target_email = f"=1+1-{unique_part}@example.com"
    signup_resp = await client.post(
        "/auth/signup", json={"name": "CSV Email Test", "email": target_email, "password": PASSWORD}
    )
    assert signup_resp.status_code == 200
    created_emails.append(target_email)
    token = await account_verification_service.create_verification_token(target_email)
    await valkey_client.set(f"verify:{token}", "1", ex=600)
    verify_resp = await client.post("/auth/verify-account", json={"token": token})
    assert verify_resp.status_code == 200
    await assign_policies(target_email, [SELF_SERVICE_POLICY_NAME])

    await client.post("/auth/login", json={"email": admin_email, "password": PASSWORD})
    resp = await client.get("/users/export", params={"search": unique_part})

    assert resp.status_code == 200
    rows = list(csv.reader(io.StringIO(resp.text)))
    header, *data_rows = rows
    email_col_index = header.index("email")
    assert len(data_rows) == 1
    assert data_rows[0][email_col_index] == f"'{target_email}"


@pytest.mark.asyncio
async def test_export_rejects_a_filtered_set_larger_than_the_configured_max(client, created_emails, monkeypatch):
    admin_email = unique_email("admin")
    await create_admin(client, created_emails, admin_email)

    # Set below the real row count so this exercises the cap without
    # needing to actually create that many rows.
    monkeypatch.setattr(settings, "USER_EXPORT_MAX_ROWS", 0)

    await client.post("/auth/login", json={"email": admin_email, "password": PASSWORD})
    resp = await client.get("/users/export")

    assert resp.status_code == 400
    assert resp.json()["code"] == "EXPORT_TOO_LARGE"
