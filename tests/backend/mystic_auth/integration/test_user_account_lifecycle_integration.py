# tests/backend/mystic_auth/integration/test_user_account_lifecycle_integration.py
#
# End-to-end coverage for system-only privileged role assignment and the
# account-lifecycle routes (soft delete, purge, reactivate) plus
# admin-driven password change (user_management_routes.py) against the real
# ASGI app, real PostgreSQL, and real Redis (see conftest.py). Split out of
# what used to be one 629-line test_user_management_routes_integration.py:
# this half covers changes to an account's standing (deleted/purged/
# reactivated, or another device's session revoked by a password reset);
# test_user_list_and_update_integration.py covers viewing/editing an
# existing account.
import pytest
from backend.mystic_auth.database.connection import database
from backend.mystic_auth.user_crud.user_crud_collector import user_crud
from backend.mystic_auth.user_table.user_model import UserRole

from .user_test_accounts import (
    PASSWORD,
    create_admin,
    create_system_user,
    create_verified_user,
    post_with_refresh_cookie,
    unique_email,
)

# ---------------------------- System privileges ----------------------------

@pytest.mark.asyncio
async def test_system_user_can_assign_system_role(client, created_emails):
    system_email = unique_email("system")
    target_email = unique_email("target")
    await create_verified_user(client, created_emails, target_email)
    await create_system_user(client, created_emails, system_email)

    resp = await client.patch(f"/users/{target_email}/role", json={"role": "system"})
    assert resp.status_code == 200

    async with database.async_session() as session:
        user = await user_crud.get_by_email(target_email, session)
        assert user.role == UserRole.system


# ---------------------------- Account lifecycle: soft delete / purge / reactivate ----------------------------

@pytest.mark.asyncio
async def test_admin_delete_soft_deletes_a_user(client, created_emails):
    # DELETE /users/{email} is the default, reversible deletion flow: the
    # row survives (preserving audit history / FK-referencing rows) with
    # is_active=False + deleted_at set, not a hard delete.
    admin_email = unique_email("admin")
    target_email = unique_email("target")
    await create_verified_user(client, created_emails, target_email)
    await create_admin(client, created_emails, admin_email)

    resp = await client.delete(f"/users/{target_email}")
    assert resp.status_code == 200

    async with database.async_session() as session:
        user = await user_crud.get_by_email(target_email, session)
        assert user is not None  # row still exists, this is a soft delete
        assert user.is_active is False
        assert user.deleted_at is not None


@pytest.mark.asyncio
async def test_soft_deleted_user_cannot_login(client, created_emails):
    admin_email = unique_email("admin")
    target_email = unique_email("target")
    await create_verified_user(client, created_emails, target_email)
    await create_admin(client, created_emails, admin_email)

    resp = await client.delete(f"/users/{target_email}")
    assert resp.status_code == 200

    login_resp = await client.post(
        "/auth/login", json={"email": target_email, "password": PASSWORD}
    )
    assert login_resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_soft_delete_revokes_the_deleted_users_active_session(client, created_emails):
    # A deleted account's existing refresh token must stop working
    # immediately, not just "eventually, once it expires on its own"; see
    # delete_any_user's Step 4 in user_management_routes.py.
    admin_email = unique_email("admin")
    target_email = unique_email("target")
    await create_verified_user(client, created_emails, target_email)
    # Capture the just-logged-in target user's own refresh token before the
    # shared client's cookie jar gets overwritten by the admin login below.
    target_refresh_token = client.cookies.get("refresh_token")
    assert target_refresh_token

    await create_admin(client, created_emails, admin_email)  # overwrites the client's cookie jar

    resp = await client.delete(f"/users/{target_email}")
    assert resp.status_code == 200

    # The deleted user's OLD refresh token, presented independently of the
    # (now admin-owned) cookie jar, must be rejected.
    refresh_resp = await post_with_refresh_cookie(client, "/auth/refresh/", target_refresh_token)
    assert refresh_resp.status_code == 401


@pytest.mark.asyncio
async def test_logout_after_admin_password_change_for_another_user_still_succeeds_and_clears_cookies(
    client, created_emails
):
    # "Other users" variant of the bug report: an admin-driven password
    # change (PUT /users/{email}) revokes the TARGET account's sessions,
    # not the admin's own, so the target, still holding their own
    # now-revoked refresh_token cookie from before the admin acted, must
    # be able to log out cleanly too, not just the self-service path.
    target_email = unique_email("target")
    target_login = await create_verified_user(client, created_emails, target_email)
    target_refresh_token = target_login.cookies["refresh_token"]

    admin_email = unique_email("admin")
    # Logs in as admin on the same shared client, replacing the cookie jar
    # this mirrors a real second browser/session, not the target's own tab.
    await create_admin(client, created_emails, admin_email)

    admin_update_resp = await client.put(
        f"/users/{target_email}", json={"password": "NewStrongPass456!"}
    )
    assert admin_update_resp.status_code == 200

    # The target's own now-revoked cookie, explicitly presented: the jar
    # currently holds the admin's session, not the target's.
    logout_resp = await post_with_refresh_cookie(client, "/auth/logout", target_refresh_token)

    assert logout_resp.status_code == 200
    # The response's Set-Cookie deletes "refresh_token" at path=/auth
    # regardless of whose value the jar currently holds under that same
    # (name, path) key, so this also proves the admin's own still-live
    # refresh_token cookie doesn't survive the target's logout call.
    assert not any(cookie.name == "refresh_token" for cookie in client.cookies.jar)


@pytest.mark.asyncio
async def test_admin_password_change_rejects_same_password(client, created_emails):
    admin_email = unique_email("admin")
    target_email = unique_email("target")
    await create_verified_user(client, created_emails, target_email)
    await create_admin(client, created_emails, admin_email)

    resp = await client.put(f"/users/{target_email}", json={"password": PASSWORD})

    assert resp.status_code == 400
    assert "different from the current password" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_admin_password_change_does_not_require_admins_current_password(client, created_emails):
    # PUT /users/{email} reuses UserUpdate, but the current-password check
    # only applies to the self-service route (update_my_profile); an admin
    # changing someone else's password authenticates via their own
    # users:update_any permission, not by proving the target's old password.
    admin_email = unique_email("admin")
    target_email = unique_email("target")
    await create_verified_user(client, created_emails, target_email)
    await create_admin(client, created_emails, admin_email)

    resp = await client.put(f"/users/{target_email}", json={"password": "AdminSetPass456!"})

    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_admin_password_change_revokes_targets_existing_sessions(client, created_emails):
    admin_email = unique_email("admin")
    target_email = unique_email("target")
    target_login_resp = await create_verified_user(client, created_emails, target_email)
    target_refresh_token = target_login_resp.cookies["refresh_token"]

    await create_admin(client, created_emails, admin_email)  # overwrites the client's cookie jar

    update_resp = await client.put(
        f"/users/{target_email}", json={"password": "NewStrongPass456!"}
    )
    assert update_resp.status_code == 200

    refresh_resp = await post_with_refresh_cookie(client, "/auth/refresh/", target_refresh_token)
    assert refresh_resp.status_code == 401


@pytest.mark.asyncio
async def test_admin_without_purge_permission_cannot_purge(client, created_emails):
    # users:purge is granted only by system_superuser: an admin holding
    # only user_administration (which includes users:delete_any) does not
    # have it; hard delete is a deliberately separate, more sensitive action.
    admin_email = unique_email("admin")
    target_email = unique_email("target")
    await create_verified_user(client, created_emails, target_email)
    await create_admin(client, created_emails, admin_email)

    resp = await client.delete(f"/users/{target_email}/purge")
    assert resp.status_code == 403

    async with database.async_session() as session:
        user = await user_crud.get_by_email(target_email, session)
        assert user is not None  # untouched: the purge was rejected


@pytest.mark.asyncio
async def test_system_user_can_purge_a_user(client, created_emails):
    system_email = unique_email("system")
    target_email = unique_email("target")
    await create_verified_user(client, created_emails, target_email)
    await create_system_user(client, created_emails, system_email)

    resp = await client.delete(f"/users/{target_email}/purge")
    assert resp.status_code == 200

    async with database.async_session() as session:
        user = await user_crud.get_by_email(target_email, session)
        assert user is None  # row permanently gone


@pytest.mark.asyncio
async def test_admin_cannot_purge_system_user(client, created_emails):
    admin_email = unique_email("admin")
    system_email = unique_email("system")
    await create_system_user(client, created_emails, system_email)
    await create_admin(client, created_emails, admin_email)

    resp = await client.delete(f"/users/{system_email}/purge")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_system_user_can_reactivate_a_soft_deleted_user(client, created_emails):
    system_email = unique_email("system")
    target_email = unique_email("target")
    await create_verified_user(client, created_emails, target_email)
    await create_system_user(client, created_emails, system_email)

    delete_resp = await client.delete(f"/users/{target_email}")
    assert delete_resp.status_code == 200

    reactivate_resp = await client.patch(f"/users/{target_email}/reactivate")
    assert reactivate_resp.status_code == 200
    assert reactivate_resp.json()["is_active"] is True
    assert reactivate_resp.json()["deleted_at"] is None

    async with database.async_session() as session:
        user = await user_crud.get_by_email(target_email, session)
        assert user.is_active is True
        assert user.deleted_at is None

    # The reactivated account can log in again with its original password.
    login_resp = await client.post(
        "/auth/login", json={"email": target_email, "password": PASSWORD}
    )
    assert login_resp.status_code == 200


@pytest.mark.asyncio
async def test_reactivate_rejects_a_never_deleted_user(client, created_emails):
    system_email = unique_email("system")
    target_email = unique_email("target")
    await create_verified_user(client, created_emails, target_email)
    await create_system_user(client, created_emails, system_email)

    resp = await client.patch(f"/users/{target_email}/reactivate")
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_admin_without_reactivate_permission_cannot_reactivate(client, created_emails):
    # users:reactivate is granted only by system_superuser, same tier as
    # users:purge, restoring access is more sensitive than day-to-day
    # user administration.
    admin_email = unique_email("admin")
    target_email = unique_email("target")
    await create_verified_user(client, created_emails, target_email)
    await create_admin(client, created_emails, admin_email)

    delete_resp = await client.delete(f"/users/{target_email}")
    assert delete_resp.status_code == 200

    resp = await client.patch(f"/users/{target_email}/reactivate")
    assert resp.status_code == 403
