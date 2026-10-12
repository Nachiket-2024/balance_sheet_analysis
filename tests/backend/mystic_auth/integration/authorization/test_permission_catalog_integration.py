# tests/backend/mystic_auth/integration/authorization/test_permission_catalog_integration.py
#
# End-to-end coverage for permission_catalog_routes.py: the read-only,
# code-defined action vocabulary (authorization/permissions_catalog.py) an
# admin picks from when granting a direct permission or authoring a policy.
import pytest

from backend.mystic_auth.authorization.permissions import Permission
from backend.mystic_auth.authorization.permissions_catalog import PERMISSION_CATALOG
from backend.mystic_auth.authorization.policies.default_policies import (
    SELF_SERVICE_POLICY_NAME,
)

from .authorization_test_accounts import (
    PASSWORD,
    create_system_user,
    create_user_with_custom_policy_actions,
    create_verified_user,
    unique_email,
)


@pytest.mark.asyncio
async def test_permission_catalog_returned_for_caller_with_permissions_read(client, created_emails):
    system_email = unique_email("system")
    await create_system_user(client, created_emails, system_email)

    await client.post("/auth/login", json={"email": system_email, "password": PASSWORD})
    resp = await client.get("/authorization/permissions/catalog")

    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == len(PERMISSION_CATALOG)
    actions = {entry["action"] for entry in body}
    assert actions == {member.value for member in Permission}
    for entry in body:
        assert entry["resource_type"]
        assert entry["description"]


@pytest.mark.asyncio
async def test_permission_catalog_denied_without_permissions_read(client, created_emails):
    target_email = unique_email("target")
    await create_verified_user(client, created_emails, target_email, [SELF_SERVICE_POLICY_NAME])

    await client.post("/auth/login", json={"email": target_email, "password": PASSWORD})
    resp = await client.get("/authorization/permissions/catalog")

    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_permission_catalog_returned_for_caller_with_only_policies_create(client, created_emails):
    """A caller holding policies:create alone (no permissions:read) still
    needs this catalog to populate the Policy create form's actions
    multi-select - see CATALOG_READ_DEPENDENCY's own docstring for why this
    is gated by "any of" rather than permissions:read alone."""
    target_email = unique_email("creator")
    await create_user_with_custom_policy_actions(client, created_emails, target_email, ["policies:create"])

    await client.post("/auth/login", json={"email": target_email, "password": PASSWORD})
    resp = await client.get("/authorization/permissions/catalog")

    assert resp.status_code == 200
    assert len(resp.json()) == len(PERMISSION_CATALOG)


@pytest.mark.asyncio
async def test_permission_catalog_returned_for_caller_with_only_policies_update(client, created_emails):
    target_email = unique_email("updater")
    await create_user_with_custom_policy_actions(client, created_emails, target_email, ["policies:update"])

    await client.post("/auth/login", json={"email": target_email, "password": PASSWORD})
    resp = await client.get("/authorization/permissions/catalog")

    assert resp.status_code == 200
    assert len(resp.json()) == len(PERMISSION_CATALOG)


@pytest.mark.asyncio
async def test_permission_catalog_returned_for_caller_with_only_permissions_grant(client, created_emails):
    """A caller holding permissions:grant alone (no permissions:read) still
    needs this catalog to populate UserPermissionsDialog/
    BulkPermissionGrantDialog's action dropdown - granted via the real API
    (not create_user_with_custom_policy_actions, which hardcodes
    resource_type="policies" - permissions:grant needs resource_type
    "permissions", or the policy-evaluation engine's own resource_type
    match would reject it before this test ever exercised the catalog
    route's own gating)."""
    system_email = unique_email("system")
    target_email = unique_email("granter")
    await create_verified_user(client, created_emails, target_email, [SELF_SERVICE_POLICY_NAME])
    await create_system_user(client, created_emails, system_email)

    await client.post("/auth/login", json={"email": system_email, "password": PASSWORD})
    grant_resp = await client.post(
        f"/authorization/users/{target_email}/permissions",
        json={"action": "permissions:grant", "resource_type": "permissions"},
    )
    assert grant_resp.status_code == 200

    await client.post("/auth/login", json={"email": target_email, "password": PASSWORD})
    resp = await client.get("/authorization/permissions/catalog")

    assert resp.status_code == 200
    assert len(resp.json()) == len(PERMISSION_CATALOG)


@pytest.mark.asyncio
async def test_permission_catalog_denied_for_caller_with_unrelated_policies_action(client, created_emails):
    """policies:delete/read alone doesn't need the catalog (deleting/
    viewing existing policies never involves picking from the action
    vocabulary), so it isn't in CATALOG_READ_DEPENDENCY's allow-list."""
    target_email = unique_email("deleter")
    await create_user_with_custom_policy_actions(client, created_emails, target_email, ["policies:delete"])

    await client.post("/auth/login", json={"email": target_email, "password": PASSWORD})
    resp = await client.get("/authorization/permissions/catalog")

    assert resp.status_code == 403
