# tests/backend/mystic_auth/integration/authorization/test_bulk_role_assignment_integration.py
#
# End-to-end coverage for backend/mystic_auth/api/pbac_routes/bulk/bulk_role_routes.py:
# setting the (display/grouping-only, non-PBAC) role field for many users in
# one request. See test_bulk_policy_assignment_integration.py's module
# docstring for the split rationale (one file per bulk domain, each kept
# ~300 lines).
import pytest

from backend.mystic_auth.authorization.policies.default_policies import (
    SELF_SERVICE_POLICY_NAME,
)
from backend.mystic_auth.database.connection import database
from backend.mystic_auth.user.user_crud_collector import user_crud
from backend.mystic_auth.user.user_model import UserRole

from .authorization_test_accounts import (
    PASSWORD,
    create_system_user,
    create_verified_user,
    unique_email,
)


@pytest.mark.asyncio
async def test_bulk_update_role_sets_role_for_every_selected_user(client, created_emails):
    system_email = unique_email("system")
    target_a = unique_email("bulk-role-a")
    target_b = unique_email("bulk-role-b")
    await create_verified_user(client, created_emails, target_a, [SELF_SERVICE_POLICY_NAME])
    await create_verified_user(client, created_emails, target_b, [SELF_SERVICE_POLICY_NAME])
    await create_system_user(client, created_emails, system_email)

    await client.post("/auth/login", json={"email": system_email, "password": PASSWORD})
    resp = await client.post(
        "/authorization/bulk/users/role",
        json={"items": [
            {"user_email": target_a, "role": "admin"},
            {"user_email": target_b, "role": "admin"},
        ]},
    )
    assert resp.status_code == 200
    assert resp.json()["success_count"] == 2

    # No GET /users/{email} exists - list with a search filter instead,
    # same as the frontend's users table does.
    list_resp = await client.get("/users/", params={"search": target_a})
    assert list_resp.status_code == 200
    matches = [u for u in list_resp.json() if u["email"] == target_a]
    assert len(matches) == 1
    assert matches[0]["role"] == "admin"


@pytest.mark.asyncio
async def test_bulk_update_role_blocks_system_target_but_still_applies_other_items(client, created_emails):
    """Same per-item safeguard as the single-item PATCH /{email}/role:
    a system-role user's role can never be changed - checked per item in
    the batch, without blocking the other, valid items."""
    system_email = unique_email("system")
    protected_system_email = unique_email("bulk-protected-system")
    ordinary_target = unique_email("bulk-role-ordinary")
    await create_system_user(client, created_emails, system_email)
    await create_verified_user(client, created_emails, protected_system_email, [SELF_SERVICE_POLICY_NAME])
    await create_verified_user(client, created_emails, ordinary_target, [SELF_SERVICE_POLICY_NAME])

    # authorization_test_accounts.create_system_user only assigns the
    # system_superuser *policy*; it never sets the (display-only, non-PBAC)
    # role column. The guard under test triggers on the role column itself,
    # so set it directly here.
    async with database.async_session() as session:
        user = await user_crud.get_by_email(protected_system_email, session)
        await user_crud.update_role(db_obj=user, role=UserRole.system, db=session)

    await client.post("/auth/login", json={"email": system_email, "password": PASSWORD})
    resp = await client.post(
        "/authorization/bulk/users/role",
        json={"items": [
            {"user_email": protected_system_email, "role": "admin"},
            {"user_email": ordinary_target, "role": "admin"},
        ]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success_count"] == 1
    assert body["error_count"] == 1
    statuses = {r["user_email"]: (r["status"], r["error"]) for r in body["results"]}
    assert statuses[protected_system_email][0] == "error"
    assert statuses[ordinary_target][0] == "success"


@pytest.mark.asyncio
async def test_bulk_update_role_blocks_self_target_but_still_applies_other_items(client, created_emails):
    """Same self-role-change guard as the single-item PATCH /{email}/role:
    a caller can never relabel themselves through this endpoint, even
    inside a batch that also targets other, valid users."""
    system_email = unique_email("system")
    ordinary_target = unique_email("bulk-role-other")
    await create_system_user(client, created_emails, system_email)
    await create_verified_user(client, created_emails, ordinary_target, [SELF_SERVICE_POLICY_NAME])

    await client.post("/auth/login", json={"email": system_email, "password": PASSWORD})
    resp = await client.post(
        "/authorization/bulk/users/role",
        json={"items": [
            {"user_email": system_email, "role": "admin"},
            {"user_email": ordinary_target, "role": "admin"},
        ]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success_count"] == 1
    assert body["error_count"] == 1
    statuses = {r["user_email"]: (r["status"], r["error"]) for r in body["results"]}
    assert statuses[system_email] == ("error", "CANNOT_CHANGE_OWN_ROLE")
    assert statuses[ordinary_target][0] == "success"


@pytest.mark.asyncio
async def test_bulk_update_role_reports_invalid_role_without_blocking_other_items(client, created_emails):
    system_email = unique_email("system")
    target_a = unique_email("bulk-invalid-role")
    target_b = unique_email("bulk-valid-role")
    await create_verified_user(client, created_emails, target_a, [SELF_SERVICE_POLICY_NAME])
    await create_verified_user(client, created_emails, target_b, [SELF_SERVICE_POLICY_NAME])
    await create_system_user(client, created_emails, system_email)

    await client.post("/auth/login", json={"email": system_email, "password": PASSWORD})
    resp = await client.post(
        "/authorization/bulk/users/role",
        json={"items": [
            {"user_email": target_a, "role": "not_a_real_role"},
            {"user_email": target_b, "role": "admin"},
        ]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success_count"] == 1
    assert body["error_count"] == 1
    statuses = {r["user_email"]: (r["status"], r["error"]) for r in body["results"]}
    assert statuses[target_a] == ("error", "INVALID_ROLE")
    assert statuses[target_b][0] == "success"
