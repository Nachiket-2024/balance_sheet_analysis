# tests/backend/mystic_auth/integration/user_crud/test_user_admin_lifecycle_valkey_outage_integration.py
#
# End-to-end coverage for the "Valkey outage failure modes are inconsistent"
# fix as it applies to admin-driven account-lifecycle actions: delete,
# purge, and password change (user_lifecycle_routes.py,
# user_management_update_routes.py), against the real ASGI app, real
# PostgreSQL, and real Valkey (see conftest.py). Kept in its own file rather
# than added to test_user_account_lifecycle_integration.py, to stay under
# the repo's file-length guideline.
import pytest

from backend.mystic_auth.database.connection import database
from backend.mystic_auth.user.user_crud_collector import user_crud

from .user_test_accounts import (
    create_admin,
    create_system_user,
    create_verified_user,
    unique_email,
)


def _fail_token_version_bump(mocker):
    # bump_account_version is a bound method captured from TokenVersionStore
    # at import time (see jwt_service.py's own comment on this), so patching
    # the class doesn't reach it. Patch the jwt_service instance directly.
    return mocker.patch(
        "backend.mystic_auth.auth.token_logic.jwt_service.jwt_service.bump_account_version",
        new_callable=mocker.AsyncMock,
        return_value=False,
    )


@pytest.mark.asyncio
async def test_admin_delete_still_soft_deletes_when_session_revocation_cant_be_confirmed(client, created_emails, mocker):
    # The soft-delete write itself (Postgres, independent of Valkey) must
    # still succeed even if the account-version bump can't be confirmed:
    # an admin shouldn't see an error for an action that actually went through.
    admin_email = unique_email("admin")
    target_email = unique_email("target")
    await create_verified_user(client, created_emails, target_email)
    await create_admin(client, created_emails, admin_email)

    _fail_token_version_bump(mocker)

    resp = await client.delete(f"/users/{target_email}")
    assert resp.status_code == 200

    async with database.async_session() as session:
        user = await user_crud.get_by_email(target_email, session)
        assert user.is_active is False
        assert user.deleted_at is not None


@pytest.mark.asyncio
async def test_admin_purge_is_blocked_with_503_when_session_revocation_cant_be_confirmed(client, created_emails, mocker):
    # Unlike a reversible soft delete, purge is irreversible and revokes
    # sessions before deleting the row, so an unconfirmed revoke must fail
    # closed: block the purge rather than delete an account whose sessions
    # might still be alive.
    # USERS_DELETE_ANY isn't part of the default admin policy set (see
    # test_admin_without_purge_permission_cannot_purge in
    # test_user_account_lifecycle_integration.py); a system-superuser
    # account is what actually holds it.
    system_email = unique_email("system")
    target_email = unique_email("target")
    await create_verified_user(client, created_emails, target_email)
    await create_system_user(client, created_emails, system_email)

    delete_resp = await client.delete(f"/users/{target_email}")
    assert delete_resp.status_code == 200

    _fail_token_version_bump(mocker)

    purge_resp = await client.delete(f"/users/{target_email}/purge")
    assert purge_resp.status_code == 503
    assert purge_resp.json()["code"] == "SESSION_REVOCATION_UNAVAILABLE"

    # The row must still exist: the purge was genuinely blocked, not
    # partially applied.
    async with database.async_session() as session:
        user = await user_crud.get_by_email(target_email, session)
        assert user is not None


@pytest.mark.asyncio
async def test_admin_password_change_reports_sessions_revoked_false_when_valkey_is_unreachable(client, created_emails, mocker):
    admin_email = unique_email("admin")
    target_email = unique_email("target")
    await create_verified_user(client, created_emails, target_email)
    await create_admin(client, created_emails, admin_email)

    _fail_token_version_bump(mocker)

    resp = await client.put(f"/users/{target_email}", json={"password": "NewStrongPass456!"})

    assert resp.status_code == 200
    assert resp.json()["sessions_revoked"] is False

    # The password itself really did change.
    login_resp = await client.post(
        "/auth/login", json={"email": target_email, "password": "NewStrongPass456!"}
    )
    assert login_resp.status_code == 200


@pytest.mark.asyncio
async def test_admin_password_change_reports_sessions_revoked_true_on_success(client, created_emails):
    admin_email = unique_email("admin")
    target_email = unique_email("target")
    await create_verified_user(client, created_emails, target_email)
    await create_admin(client, created_emails, admin_email)

    resp = await client.put(f"/users/{target_email}", json={"password": "NewStrongPass456!"})

    assert resp.status_code == 200
    assert resp.json()["sessions_revoked"] is True
