# tests/backend/mystic_auth/integration/user/test_user_self_service_account_deletion_integration.py
#
# End-to-end coverage for DELETE /users/me and its OAuth-only
# confirm-delete flow (user_self_service_routes.py,
# account_deletion_service.py). See test_user_self_service_routes_
# integration.py for GET/PUT /users/me coverage.
import pytest

from backend.mystic_auth.database.connection import database
from backend.mystic_auth.user.user_crud_collector import user_crud
from backend.mystic_auth.user_lifecycle.account_deletion_service import (
    account_deletion_service,
)
from backend.mystic_auth.valkey.client import valkey_client

from .user_test_accounts import (
    PASSWORD,
    create_system_user,
    create_verified_user,
    post_with_refresh_cookie,
    unique_email,
)


@pytest.mark.asyncio
async def test_self_delete_soft_deletes_own_account(client, created_emails):
    # Self-service counterpart to delete_any_user: same soft-delete
    # mechanics, acting on the caller's own row instead of a path email.
    email = unique_email()
    await create_verified_user(client, created_emails, email)

    resp = await client.request("DELETE", "/users/me", json={"current_password": PASSWORD})
    assert resp.status_code == 200

    async with database.async_session() as session:
        user = await user_crud.get_by_email(email, session)
        assert user is not None  # soft delete: row still exists
        assert user.is_active is False
        assert user.deleted_at is not None


@pytest.mark.asyncio
async def test_self_delete_still_soft_deletes_when_session_revocation_cant_be_confirmed(client, created_emails, mocker):
    # The soft-delete write (Postgres) must still succeed even if the
    # account-version bump (Valkey) can't be confirmed: the account really
    # is deleted, so this must not surface as an error to the caller.
    email = unique_email()
    await create_verified_user(client, created_emails, email)

    # bump_account_version is a bound-method reference captured at import
    # time, so patching the class wouldn't reach it; patch the instance
    # attribute directly instead.
    mocker.patch(
        "backend.mystic_auth.auth.token_logic.jwt_service.jwt_service.bump_account_version",
        new_callable=mocker.AsyncMock,
        return_value=False,
    )

    resp = await client.request("DELETE", "/users/me", json={"current_password": PASSWORD})
    assert resp.status_code == 200

    async with database.async_session() as session:
        user = await user_crud.get_by_email(email, session)
        assert user.is_active is False
        assert user.deleted_at is not None


@pytest.mark.asyncio
async def test_self_delete_requires_current_password(client, created_emails):
    email = unique_email()
    await create_verified_user(client, created_emails, email)

    resp = await client.request("DELETE", "/users/me", json={})
    assert resp.status_code == 400
    assert "current password" in resp.json()["detail"].lower()

    async with database.async_session() as session:
        user = await user_crud.get_by_email(email, session)
        assert user.is_active is True  # rejected, so no deletion happened


@pytest.mark.asyncio
async def test_self_delete_rejects_wrong_current_password(client, created_emails):
    email = unique_email()
    await create_verified_user(client, created_emails, email)

    resp = await client.request("DELETE", "/users/me", json={"current_password": "WrongPassword1"})
    assert resp.status_code == 400
    assert "current password" in resp.json()["detail"].lower()

    # The rejected delete had no effect: account is still active and usable.
    async with database.async_session() as session:
        user = await user_crud.get_by_email(email, session)
        assert user.is_active is True

    login_resp = await client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert login_resp.status_code == 200


@pytest.mark.asyncio
async def test_system_user_cannot_self_delete(client, created_emails):
    # Same target-account guard as the admin routes: the system account
    # must never disappear via any route, self-service included.
    email = unique_email("system")
    await create_system_user(client, created_emails, email)

    resp = await client.request("DELETE", "/users/me", json={"current_password": PASSWORD})
    assert resp.status_code == 403

    async with database.async_session() as session:
        user = await user_crud.get_by_email(email, session)
        assert user.is_active is True


@pytest.mark.asyncio
async def test_self_delete_revokes_existing_sessions(client, created_emails):
    email = unique_email()
    login_resp = await create_verified_user(client, created_emails, email)
    refresh_token = login_resp.cookies["refresh_token"]

    resp = await client.request("DELETE", "/users/me", json={"current_password": PASSWORD})
    assert resp.status_code == 200

    # The old refresh token must stop working immediately.
    refresh_resp = await post_with_refresh_cookie(client, "/auth/refresh/", refresh_token)
    assert refresh_resp.status_code == 401

    # And the account can no longer log back in.
    relogin_resp = await client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert relogin_resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_self_delete_clears_auth_cookies_on_success(client, created_emails):
    # Every other endpoint that ends a session clears both auth cookies;
    # this checks DELETE /users/me does too, instead of leaving the
    # browser holding dead cookies for an already-deleted account.
    email = unique_email()
    await create_verified_user(client, created_emails, email)
    assert any(cookie.name == "refresh_token" for cookie in client.cookies.jar)

    resp = await client.request("DELETE", "/users/me", json={"current_password": PASSWORD})
    assert resp.status_code == 200

    assert not any(cookie.name == "refresh_token" for cookie in client.cookies.jar)
    assert not any(cookie.name == "access_token" for cookie in client.cookies.jar)


# ------------------- Self-service account deletion: OAuth-only accounts -------------------
#
# An OAuth-only account (hashed_password=None) has no password to confirm
# with, so a stolen session cookie alone would otherwise be enough to
# delete it. Instead DELETE /users/me only sends a confirmation email, and
# POST /users/me/confirm-delete (unauthenticated; the token is the proof)
# actually performs the deletion.

async def _make_oauth_only_user(client, created_emails, email: str):
    await create_verified_user(client, created_emails, email)
    async with database.async_session() as session:
        user = await user_crud.get_by_email(email, session)
        user.hashed_password = None
        session.add(user)
        await session.commit()


async def _make_oauth_only_user_and_login(client, created_emails, email: str):
    login_resp = await create_verified_user(client, created_emails, email)
    async with database.async_session() as session:
        user = await user_crud.get_by_email(email, session)
        user.hashed_password = None
        session.add(user)
        await session.commit()
    return login_resp


@pytest.mark.asyncio
async def test_self_delete_on_oauth_only_account_does_not_require_current_password(client, created_emails):
    email = unique_email()
    await _make_oauth_only_user(client, created_emails, email)

    resp = await client.request("DELETE", "/users/me", json={})
    assert resp.status_code == 200
    assert resp.json()["confirmation_required"] is True

    # Not deleted yet: only a confirmation email was sent.
    async with database.async_session() as session:
        user = await user_crud.get_by_email(email, session)
        assert user.is_active is True
        assert user.deleted_at is None


@pytest.mark.asyncio
async def test_self_delete_on_oauth_only_account_does_not_revoke_the_calling_session(client, created_emails):
    email = unique_email()
    await _make_oauth_only_user(client, created_emails, email)

    resp = await client.request("DELETE", "/users/me", json={})
    assert resp.status_code == 200

    me_resp = await client.get("/users/me")
    assert me_resp.status_code == 200


@pytest.mark.asyncio
async def test_confirm_delete_actually_deletes_and_revokes_sessions(client, created_emails):
    email = unique_email()
    login_resp = await _make_oauth_only_user_and_login(client, created_emails, email)
    refresh_token = login_resp.cookies["refresh_token"]

    delete_resp = await client.request("DELETE", "/users/me", json={})
    assert delete_resp.status_code == 200

    token = await account_deletion_service.create_account_deletion_token(email)
    await valkey_client.set(f"account_delete:{token}", "1", ex=600)

    confirm_resp = await client.post("/users/me/confirm-delete", json={"token": token})
    assert confirm_resp.status_code == 200

    async with database.async_session() as session:
        user = await user_crud.get_by_email(email, session)
        assert user.is_active is False
        assert user.deleted_at is not None

    refresh_resp = await post_with_refresh_cookie(client, "/auth/refresh/", refresh_token)
    assert refresh_resp.status_code == 401


@pytest.mark.asyncio
async def test_confirm_delete_token_is_single_use(client, created_emails):
    email = unique_email()
    await _make_oauth_only_user(client, created_emails, email)

    token = await account_deletion_service.create_account_deletion_token(email)
    await valkey_client.set(f"account_delete:{token}", "1", ex=600)

    first_resp = await client.post("/users/me/confirm-delete", json={"token": token})
    assert first_resp.status_code == 200

    second_resp = await client.post("/users/me/confirm-delete", json={"token": token})
    assert second_resp.status_code == 400


@pytest.mark.asyncio
async def test_confirm_delete_rejects_token_never_persisted_in_valkey(client, created_emails):
    # A validly-signed token that was never actually issued (never written
    # to Valkey) must be rejected, same as an already-used one.
    email = unique_email()
    await _make_oauth_only_user(client, created_emails, email)

    token = await account_deletion_service.create_account_deletion_token(email)

    resp = await client.post("/users/me/confirm-delete", json={"token": token})
    assert resp.status_code == 400

    async with database.async_session() as session:
        user = await user_crud.get_by_email(email, session)
        assert user.is_active is True


@pytest.mark.asyncio
async def test_confirm_delete_rejects_garbage_token(client, created_emails):
    resp = await client.post("/users/me/confirm-delete", json={"token": "not-a-real-jwt"})
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_confirm_delete_one_accounts_token_cannot_delete_a_different_account(client, created_emails):
    # The token embeds its owning account's email as a signed claim, so it
    # can only ever delete that same account.
    victim_email = unique_email("victim")
    other_email = unique_email("bystander")
    await _make_oauth_only_user(client, created_emails, victim_email)
    await _make_oauth_only_user(client, created_emails, other_email)

    token = await account_deletion_service.create_account_deletion_token(victim_email)
    await valkey_client.set(f"account_delete:{token}", "1", ex=600)

    resp = await client.post("/users/me/confirm-delete", json={"token": token})
    assert resp.status_code == 200

    async with database.async_session() as session:
        victim = await user_crud.get_by_email(victim_email, session)
        other = await user_crud.get_by_email(other_email, session)
        assert victim.is_active is False
        assert other.is_active is True
