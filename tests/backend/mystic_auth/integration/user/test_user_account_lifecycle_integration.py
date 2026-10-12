# tests/backend/mystic_auth/integration/test_user_account_lifecycle_integration.py
#
# End-to-end coverage for system-only privileged role assignment and the
# account-lifecycle routes (soft delete, purge, reactivate) plus
# admin-driven password change (user_management_update_routes.py), against
# the real ASGI app, real PostgreSQL, and real Valkey (see conftest.py).
# Split out of the old 629-line test_user_management_routes_integration.py:
# this half covers changes to an account's standing (deleted/purged/
# reactivated, or a session revoked by a password reset);
# test_user_list_and_update_integration.py covers viewing/editing an
# existing account.
import pytest

from backend.mystic_auth.authorization.policies.default_policies import (
    SELF_SERVICE_POLICY_NAME,
    SYSTEM_SUPERUSER_POLICY_NAME,
    USER_MANAGEMENT_POLICY_NAME,
)
from backend.mystic_auth.database.connection import database
from backend.mystic_auth.user.user_crud_collector import user_crud
from backend.mystic_auth.user.user_model import UserRole

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
    # DELETE /users/{email} is the default, reversible flow: the row stays
    # (keeping audit history and FK-referencing rows) with is_active=False
    # and deleted_at set, not a hard delete.
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
async def test_admin_cannot_delete_their_own_account(client, created_emails):
    # The frontend disables this for the caller's own row, but that's UI
    # only; the backend must also block it, since a sole admin deleting
    # themselves would revoke their own sessions and lock them out for good.
    admin_email = unique_email("admin")
    await create_admin(client, created_emails, admin_email)

    resp = await client.delete(f"/users/{admin_email}")
    assert resp.status_code == 403

    async with database.async_session() as session:
        user = await user_crud.get_by_email(admin_email, session)
        assert user.is_active is True


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
    # A deleted account's refresh token must stop working immediately, not
    # just once it eventually expires; see delete_any_user's Step 4 in
    # user_lifecycle_routes.py.
    admin_email = unique_email("admin")
    target_email = unique_email("target")
    await create_verified_user(client, created_emails, target_email)
    # Save the target's refresh token before the admin login below
    # overwrites the shared client's cookie jar.
    target_refresh_token = client.cookies.get("refresh_token")
    assert target_refresh_token

    await create_admin(client, created_emails, admin_email)  # overwrites the client's cookie jar

    resp = await client.delete(f"/users/{target_email}")
    assert resp.status_code == 200

    # The deleted user's old refresh token, sent independently of the
    # (now admin-owned) cookie jar, must be rejected.
    refresh_resp = await post_with_refresh_cookie(client, "/auth/refresh/", target_refresh_token)
    assert refresh_resp.status_code == 401


@pytest.mark.asyncio
async def test_logout_after_admin_password_change_for_another_user_still_succeeds_and_clears_cookies(
    client, created_emails
):
    # An admin-driven password change (PUT /users/{email}) revokes the
    # TARGET account's sessions, not the admin's own. The target, still
    # holding their now-revoked refresh_token cookie from before the admin
    # acted, must still be able to log out cleanly.
    target_email = unique_email("target")
    target_login = await create_verified_user(client, created_emails, target_email)
    target_refresh_token = target_login.cookies["refresh_token"]

    admin_email = unique_email("admin")
    # Logs in as admin on the same shared client, replacing the cookie jar,
    # mirroring a real second browser/session rather than the target's tab.
    await create_admin(client, created_emails, admin_email)

    admin_update_resp = await client.put(
        f"/users/{target_email}", json={"password": "NewStrongPass456!"}
    )
    assert admin_update_resp.status_code == 200

    # Explicitly send the target's now-revoked cookie, since the jar
    # currently holds the admin's session.
    logout_resp = await post_with_refresh_cookie(client, "/auth/logout", target_refresh_token)

    assert logout_resp.status_code == 200
    # The response's Set-Cookie deletes "refresh_token" at path=/auth no
    # matter whose value the jar holds under that (name, path) key, so this
    # also proves the admin's own live cookie doesn't survive the target's
    # logout call.
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
    # only applies to the self-service route (update_my_profile). An admin
    # is authorized by their own users:update_any permission, not by
    # proving the target's old password.
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
    # users:delete_any is granted only by system_superuser. user_management
    # (which includes users:deactivate_any) does not include it: hard delete is
    # a deliberately separate, more sensitive action.
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
async def test_purge_holder_cannot_purge_their_own_account(client, created_emails):
    # Same self-lockout reasoning as the delete guard, more severe here
    # since a purge is irreversible. Uses role=user (not system) so this
    # tests the self-action guard specifically, not the separate "system
    # user cannot be purged" check that would otherwise mask it.
    email = unique_email("purge-holder")
    await create_verified_user(
        client, created_emails, email,
        policy_names=[SELF_SERVICE_POLICY_NAME, USER_MANAGEMENT_POLICY_NAME, SYSTEM_SUPERUSER_POLICY_NAME],
    )

    resp = await client.delete(f"/users/{email}/purge")
    assert resp.status_code == 403

    async with database.async_session() as session:
        user = await user_crud.get_by_email(email, session)
        assert user is not None


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
    # users:delete_any: restoring access is more sensitive than day-to-day user
    # administration.
    admin_email = unique_email("admin")
    target_email = unique_email("target")
    await create_verified_user(client, created_emails, target_email)
    await create_admin(client, created_emails, admin_email)

    delete_resp = await client.delete(f"/users/{target_email}")
    assert delete_resp.status_code == 200

    resp = await client.patch(f"/users/{target_email}/reactivate")
    assert resp.status_code == 403
