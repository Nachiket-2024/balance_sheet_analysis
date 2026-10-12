# tests/backend/mystic_auth/integration/authorization/test_policy_crud_integration.py
#
# End-to-end coverage for policy_crud_routes.py (backend/mystic_auth/api/
# pbac_routes/) against the real ASGI app, real PostgreSQL, and real Valkey:
# the authorization gate on the policy management routes, and policy
# create/read/update/delete itself. List search/filter/sort/pagination
# coverage lives in test_policy_list_integration.py, split out once this
# file passed the repo's file-length guideline.
import pytest

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

from .authorization_test_accounts import (
    cleanup_test_policies,
    create_system_user,
    create_verified_user,
    unique_email,
    unique_policy_name,
)

__all__ = ["cleanup_test_policies"]

# ---------------------------- Authorization gate on management routes ----------------------------

@pytest.mark.asyncio
async def test_unauthenticated_request_is_rejected(client):
    resp = await client.get("/authorization/policies")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_regular_user_cannot_manage_policies(client, created_emails):
    email = unique_email()
    await create_verified_user(client, created_emails, email, [SELF_SERVICE_POLICY_NAME])

    resp = await client.get("/authorization/policies")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_without_policies_read_cannot_manage_policies(client, created_emails):
    # user_management doesn't include any policies:* action; only
    # system_superuser does, so an ordinary admin must be denied here.
    email = unique_email("admin")
    await create_verified_user(client, created_emails, email, [SELF_SERVICE_POLICY_NAME, USER_MANAGEMENT_POLICY_NAME])

    resp = await client.get("/authorization/policies")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_list_policies_respects_limit_query_param(client, created_emails):
    # Regression guard: this endpoint used to read the whole table
    # unconditionally. Baseline seeded policies guarantee more than one row
    # already exists.
    email = unique_email("system")
    await create_verified_user(client, created_emails, email, [SYSTEM_SUPERUSER_POLICY_NAME])

    resp = await client.get("/authorization/policies?limit=1")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


# ---------------------------- Policy CRUD ----------------------------

@pytest.mark.asyncio
async def test_system_user_can_create_list_update_and_delete_a_policy(client, created_emails):
    system_email = unique_email("system")
    await create_system_user(client, created_emails, system_email)
    policy_name = unique_policy_name()

    create_resp = await client.post(
        "/authorization/policies",
        json={
            "name": policy_name,
            "description": "A test-only policy",
            "actions": ["projects:read"],
            "resource_type": "projects",
        },
    )
    assert create_resp.status_code == 201
    body = create_resp.json()
    assert body["name"] == policy_name
    assert body["is_active"] is True
    assert body["created_by"] == system_email

    list_resp = await client.get("/authorization/policies")
    assert list_resp.status_code == 200
    assert any(p["name"] == policy_name for p in list_resp.json())

    update_resp = await client.put(
        f"/authorization/policies/{policy_name}", json={"is_active": False}
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["is_active"] is False

    delete_resp = await client.delete(f"/authorization/policies/{policy_name}")
    assert delete_resp.status_code == 200

    get_resp = await client.get(f"/authorization/policies/{policy_name}")
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_creating_a_duplicate_named_policy_is_rejected(client, created_emails):
    system_email = unique_email("system")
    await create_system_user(client, created_emails, system_email)
    policy_name = unique_policy_name()

    payload = {
        "name": policy_name,
        "actions": ["projects:read"],
        "resource_type": "projects",
    }
    first = await client.post("/authorization/policies", json=payload)
    assert first.status_code == 201

    second = await client.post("/authorization/policies", json=payload)
    assert second.status_code == 409


@pytest.mark.asyncio
async def test_conditional_operator_cannot_create_a_broader_policy(client, created_emails):
    """Delegation keeps the caller's condition scope instead of checking only
    the action name and resource type."""
    operator_email = unique_email("operator")
    await create_verified_user(client, created_emails, operator_email, [SELF_SERVICE_POLICY_NAME])

    conditional_name = unique_policy_name()
    async with database.async_session() as session:
        await policy_repository.create(
            {
                "name": conditional_name,
                "actions": ["policies:create"],
                "resource_type": "policies",
                "conditions": {"date_range": {"start": "2000-01-01", "end": "2099-12-31"}},
            },
            session,
        )
        policy = await policy_repository.get_by_name(conditional_name, session)
        assert policy

    # The operator needs the conditional management grant, assigned directly
    # through the test database rather than through an HTTP grant endpoint.
    async with database.async_session() as session:
        account = await user_crud.get_by_email(operator_email, session)
        policy = await policy_repository.get_by_name(conditional_name, session)
        await policy_repository.assign_policy_to_user(
            user_id=account.id, policy_id=policy.id, db=session, assigned_by="test"
        )

    await client.post("/auth/login", json={"email": operator_email, "password": "StrongPass123!"})
    broad = await client.post(
        "/authorization/policies",
        json={"name": unique_policy_name(), "actions": ["policies:create"], "resource_type": "policies"},
    )
    assert broad.status_code == 403
    assert broad.json()["code"] == "CANNOT_GRANT_BROADER_CONDITIONS"


@pytest.mark.asyncio
async def test_renaming_a_policy_to_an_existing_name_is_rejected(client, created_emails):
    system_email = unique_email("system")
    await create_system_user(client, created_emails, system_email)

    first_name = unique_policy_name()
    second_name = unique_policy_name()

    first = await client.post(
        "/authorization/policies",
        json={"name": first_name, "actions": ["projects:read"], "resource_type": "projects"},
    )
    assert first.status_code == 201

    second = await client.post(
        "/authorization/policies",
        json={"name": second_name, "actions": ["projects:read"], "resource_type": "projects"},
    )
    assert second.status_code == 201

    rename_resp = await client.put(f"/authorization/policies/{first_name}", json={"name": second_name})
    assert rename_resp.status_code == 409

    # Confirm it didn't take: the original policy is still reachable under its old name.
    get_resp = await client.get(f"/authorization/policies/{first_name}")
    assert get_resp.status_code == 200
