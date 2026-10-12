# tests/backend/mystic_auth/integration/user/test_user_admin_management_integration.py
#
# End-to-end coverage for admin-side PUT /users/{email} and PATCH
# /users/{email}/role (user_management_update_routes.py), against the real
# ASGI app, real PostgreSQL, and real Valkey (see conftest.py), including
# the system-user and self-role-change guards no admin capability can
# bypass. GET /users/ listing/filtering/sorting coverage lives in
# test_user_admin_listing_integration.py, split out once this file passed
# the repo's file-length guideline; see test_user_list_and_update_integration.py
# for the base authorization-gate and role-as-metadata PBAC coverage.
import pytest

from backend.mystic_auth.database.connection import database
from backend.mystic_auth.user.user_crud_collector import user_crud
from backend.mystic_auth.user.user_model import UserRole

from .user_test_accounts import (
    PASSWORD,
    create_admin,
    create_system_user,
    create_verified_user,
    unique_email,
)


@pytest.mark.asyncio
async def test_admin_can_update_a_regular_user(client, created_emails):
    admin_email = unique_email("admin")
    target_email = unique_email("target")

    # Create the target first, in its own session, so logging in as admin
    # afterward doesn't affect it.
    await create_verified_user(client, created_emails, target_email)
    await create_admin(client, created_emails, admin_email)

    resp = await client.put(f"/users/{target_email}", json={"name": "Renamed By Admin"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "Renamed By Admin"


@pytest.mark.asyncio
async def test_admin_cannot_modify_system_user(client, created_emails):
    # Regression test: update_any_user used to lack the system-user guard
    # that delete/role-update already had, so an admin could PUT a new
    # password onto the system account and take it over. This guard is a
    # target-resource invariant, not a PBAC decision; see
    # user_management_update_routes.py's UserRole import note.
    admin_email = unique_email("admin")
    system_email = unique_email("system")
    await create_system_user(client, created_emails, system_email)
    await create_admin(client, created_emails, admin_email)

    resp = await client.put(f"/users/{system_email}", json={"password": "NewPass123!"})
    assert resp.status_code == 403

    # The system account's password must be unchanged: verify by logging
    # in with the original password.
    login_resp = await client.post(
        "/auth/login", json={"email": system_email, "password": PASSWORD}
    )
    assert login_resp.status_code == 200


@pytest.mark.asyncio
async def test_admin_cannot_delete_system_user(client, created_emails):
    admin_email = unique_email("admin")
    system_email = unique_email("system")
    await create_system_user(client, created_emails, system_email)
    await create_admin(client, created_emails, admin_email)

    resp = await client.delete(f"/users/{system_email}")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_cannot_change_system_user_role(client, created_emails):
    admin_email = unique_email("admin")
    system_email = unique_email("system")
    await create_system_user(client, created_emails, system_email)
    await create_admin(client, created_emails, admin_email)

    resp = await client.patch(f"/users/{system_email}/role", json={"role": "user"})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_cannot_assign_system_role_to_another_user(client, created_emails):
    admin_email = unique_email("admin")
    target_email = unique_email("target")
    await create_verified_user(client, created_emails, target_email)
    await create_admin(client, created_emails, admin_email)

    resp = await client.patch(f"/users/{target_email}/role", json={"role": "system"})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_cannot_change_own_role(client, created_emails):
    # Regression test: users:assign_role alone used to let its holder
    # relabel *themselves*, not just other users - harmless today since
    # UserRole is display-only everywhere in this codebase (confirmed by
    # test_admin_can_change_user_role_to_admin_and_back_via_role_endpoint
    # above having no other effect), but a future `if role == "admin"`
    # shortcut anywhere downstream would turn a self-relabel into a real
    # privilege escalation with no PBAC guard watching it. Self-role-changes
    # are blocked outright, independent of which role is requested.
    admin_email = unique_email("admin")
    await create_admin(client, created_emails, admin_email)

    resp = await client.patch(f"/users/{admin_email}/role", json={"role": "admin"})
    assert resp.status_code == 403
    assert resp.json()["code"] == "CANNOT_CHANGE_OWN_ROLE"

    async with database.async_session() as session:
        user = await user_crud.get_by_email(admin_email, session)
        assert user.role == UserRole.admin  # unchanged, not merely re-applied


@pytest.mark.asyncio
async def test_admin_can_change_user_role_to_admin_and_back_via_role_endpoint(client, created_emails):
    # Role changes are bidirectional through the single generic /role
    # endpoint; there's no separate one-directional "promote" path. An
    # admin holding only user_management (users:assign_role, not
    # users:assign_system_role) can move a non-system user to any
    # non-system role, either direction.
    admin_email = unique_email("admin")
    target_email = unique_email("target")
    await create_verified_user(client, created_emails, target_email)
    await create_admin(client, created_emails, admin_email)

    resp = await client.patch(f"/users/{target_email}/role", json={"role": "admin"})
    assert resp.status_code == 200

    async with database.async_session() as session:
        user = await user_crud.get_by_email(target_email, session)
        assert user.role == UserRole.admin

    resp = await client.patch(f"/users/{target_email}/role", json={"role": "user"})
    assert resp.status_code == 200

    async with database.async_session() as session:
        user = await user_crud.get_by_email(target_email, session)
        assert user.role == UserRole.user
