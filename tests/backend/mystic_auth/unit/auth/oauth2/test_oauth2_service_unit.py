# tests/backend/mystic_auth/unit/test_oauth2_service_unit.py
from unittest.mock import AsyncMock

import pytest
from backend.mystic_auth.auth.oauth2.oauth2_service import oauth2_service
from backend.mystic_auth.authorization.policies.default_policies import SELF_SERVICE_POLICY_NAME
from backend.mystic_auth.user_table.user_model import UserRole

MODULE = "backend.mystic_auth.auth.oauth2.oauth2_service"


class _FakeUser:
    def __init__(self, role_value="user", is_verified=True, is_active=True, hashed_password=None):
        class _Role:
            value = role_value
        self.id = 1
        self.role = _Role()
        self.is_verified = is_verified
        self.is_active = is_active
        self.hashed_password = hashed_password


class _FakePolicy:
    def __init__(self, id=1):
        self.id = id


@pytest.mark.asyncio
async def test_login_or_create_user_existing_user_does_not_write_orphaned_session_store(mocker):
    mocker.patch(f"{MODULE}.user_crud.get_by_email", return_value=_FakeUser())
    mocker.patch(f"{MODULE}.jwt_service.create_access_token", return_value="access-token")
    mocker.patch(f"{MODULE}.jwt_service.create_refresh_token", return_value="refresh-token")
    rpush_mock = mocker.patch(f"{MODULE}.redis_client.rpush", new_callable=AsyncMock)

    result = await oauth2_service.login_or_create_user(db=None, user_info={"email": "user@example.com"})

    assert result == {"access_token": "access-token", "refresh_token": "refresh-token"}
    # The old `user_tokens:{email}` list was dead code nothing ever read, and
    # grew forever with no TTL, it must no longer be written to.
    rpush_mock.assert_not_called()


@pytest.mark.asyncio
async def test_login_or_create_user_marks_unverified_existing_user_verified(mocker):
    # An existing password account that never clicked our verification email.
    # oauth2_login_handler only calls this method after confirming Google's
    # own email_verified flag, which is equally valid proof of ownership.
    mocker.patch(f"{MODULE}.user_crud.get_by_email", return_value=_FakeUser(is_verified=False))
    update_mock = mocker.patch(
        f"{MODULE}.user_crud.update_by_email",
        return_value=_FakeUser(is_verified=True),
    )
    mocker.patch(f"{MODULE}.jwt_service.create_access_token", return_value="access-token")
    mocker.patch(f"{MODULE}.jwt_service.create_refresh_token", return_value="refresh-token")

    result = await oauth2_service.login_or_create_user(db=None, user_info={"email": "user@example.com"})

    assert result == {"access_token": "access-token", "refresh_token": "refresh-token"}
    update_mock.assert_awaited_once_with(
        "user@example.com", {"is_verified": True, "hashed_password": None}, None
    )


@pytest.mark.asyncio
async def test_login_or_create_user_clears_password_on_pre_hijacked_unverified_account(mocker):
    # Pre-hijacking regression guard: an attacker can register the victim's
    # email with an attacker-chosen password and never verify it. If linking
    # only flipped is_verified without also clearing hashed_password, the
    # attacker's password would remain valid on the now-verified account,
    # letting them log in as the victim indefinitely after the victim's
    # first "Sign in with Google". The fix must clear hashed_password so the
    # attacker-set credential cannot survive the account being claimed.
    mocker.patch(
        f"{MODULE}.user_crud.get_by_email",
        return_value=_FakeUser(is_verified=False, hashed_password="attacker-set-hash"),
    )
    update_mock = mocker.patch(
        f"{MODULE}.user_crud.update_by_email",
        return_value=_FakeUser(is_verified=True, hashed_password=None),
    )
    mocker.patch(f"{MODULE}.jwt_service.create_access_token", return_value="access-token")
    mocker.patch(f"{MODULE}.jwt_service.create_refresh_token", return_value="refresh-token")

    result = await oauth2_service.login_or_create_user(db=None, user_info={"email": "victim@example.com"})

    assert result == {"access_token": "access-token", "refresh_token": "refresh-token"}
    args, _ = update_mock.call_args
    update_data = args[1]
    assert update_data["hashed_password"] is None


@pytest.mark.asyncio
async def test_login_or_create_user_rejects_reserved_system_account(mocker):
    # OAuth2 login trusts Google's email_verified alone, there is no
    # password check in this flow at all. Without this guard, anyone who
    # controls a Google account matching the (operator-chosen, potentially
    # real/Google-verifiable) email of the reserved system superuser could
    # sign in as it, entirely bypassing its password. Mirrors the identical
    # role == UserRole.system guard in user_management_routes.py's update/delete/
    # role-change endpoints.
    system_user = _FakeUser()
    system_user.role = UserRole.system
    mocker.patch(f"{MODULE}.user_crud.get_by_email", return_value=system_user)
    create_access_mock = mocker.patch(f"{MODULE}.jwt_service.create_access_token", new_callable=AsyncMock)

    result = await oauth2_service.login_or_create_user(db=None, user_info={"email": "system@example.com"})

    assert result is None
    create_access_mock.assert_not_called()


@pytest.mark.asyncio
async def test_login_or_create_user_rejects_deactivated_existing_user(mocker):
    # Mirrors login_service.py's own is_active check for password login: a
    # deactivated account must not receive fresh tokens via Google OAuth2 either.
    mocker.patch(f"{MODULE}.user_crud.get_by_email", return_value=_FakeUser(is_active=False))
    create_access_mock = mocker.patch(f"{MODULE}.jwt_service.create_access_token", new_callable=AsyncMock)

    result = await oauth2_service.login_or_create_user(db=None, user_info={"email": "deactivated@example.com"})

    assert result is None
    create_access_mock.assert_not_called()


@pytest.mark.asyncio
async def test_login_or_create_user_does_not_touch_already_verified_existing_user(mocker):
    mocker.patch(f"{MODULE}.user_crud.get_by_email", return_value=_FakeUser(is_verified=True))
    update_mock = mocker.patch(f"{MODULE}.user_crud.update_by_email")
    mocker.patch(f"{MODULE}.jwt_service.create_access_token", return_value="access-token")
    mocker.patch(f"{MODULE}.jwt_service.create_refresh_token", return_value="refresh-token")

    result = await oauth2_service.login_or_create_user(db=None, user_info={"email": "user@example.com"})

    assert result == {"access_token": "access-token", "refresh_token": "refresh-token"}
    update_mock.assert_not_called()


@pytest.mark.asyncio
async def test_login_or_create_user_creates_new_verified_user(mocker):
    mocker.patch(f"{MODULE}.user_crud.get_by_email", return_value=None)
    create_mock = mocker.patch(f"{MODULE}.user_crud.create", return_value=_FakeUser())
    mocker.patch(f"{MODULE}.policy_repository.get_by_name", return_value=_FakePolicy())
    assign_mock = mocker.patch(f"{MODULE}.policy_repository.assign_policy_to_user", new_callable=AsyncMock)
    mocker.patch(f"{MODULE}.jwt_service.create_access_token", return_value="access-token")
    mocker.patch(f"{MODULE}.jwt_service.create_refresh_token", return_value="refresh-token")

    result = await oauth2_service.login_or_create_user(
        db=None, user_info={"email": "new@example.com", "name": "New User"}
    )

    assert result == {"access_token": "access-token", "refresh_token": "refresh-token"}
    create_mock.assert_awaited_once()
    args, _ = create_mock.call_args
    user_data = args[0]
    assert user_data["email"] == "new@example.com"
    assert user_data["is_verified"] is True
    assert user_data["hashed_password"] is None
    # Role is metadata/display only and grants nothing : access comes from
    # the assigned self_service policy below, never the role. Set to the
    # same default UserRole.user password signup uses (see
    # signup_service.py), so every new account shows a role consistently
    # in the UI regardless of how it was created.
    assert user_data["role"] == UserRole.user
    assign_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_login_or_create_user_assigns_self_service_policy_to_new_user(mocker):
    mocker.patch(f"{MODULE}.user_crud.get_by_email", return_value=None)
    new_user = _FakeUser()
    new_user.id = 42
    mocker.patch(f"{MODULE}.user_crud.create", return_value=new_user)
    self_service_policy = _FakePolicy(id=7)
    get_policy_mock = mocker.patch(f"{MODULE}.policy_repository.get_by_name", return_value=self_service_policy)
    assign_mock = mocker.patch(f"{MODULE}.policy_repository.assign_policy_to_user", new_callable=AsyncMock)
    mocker.patch(f"{MODULE}.jwt_service.create_access_token", return_value="access-token")
    mocker.patch(f"{MODULE}.jwt_service.create_refresh_token", return_value="refresh-token")

    await oauth2_service.login_or_create_user(
        db="fake-db", user_info={"email": "new@example.com", "name": "New User"}
    )

    get_policy_mock.assert_awaited_once_with(SELF_SERVICE_POLICY_NAME, "fake-db")
    assign_mock.assert_awaited_once_with(
        user_id=42, policy_id=7, db="fake-db", assigned_by="system"
    )


@pytest.mark.asyncio
async def test_login_or_create_user_missing_self_service_policy_does_not_block_login(mocker):
    # Should never happen once the seeding migration has run, but a missing
    # baseline policy must not fail the login attempt outright.
    mocker.patch(f"{MODULE}.user_crud.get_by_email", return_value=None)
    mocker.patch(f"{MODULE}.user_crud.create", return_value=_FakeUser())
    mocker.patch(f"{MODULE}.policy_repository.get_by_name", return_value=None)
    assign_mock = mocker.patch(f"{MODULE}.policy_repository.assign_policy_to_user", new_callable=AsyncMock)
    mocker.patch(f"{MODULE}.jwt_service.create_access_token", return_value="access-token")
    mocker.patch(f"{MODULE}.jwt_service.create_refresh_token", return_value="refresh-token")

    result = await oauth2_service.login_or_create_user(
        db=None, user_info={"email": "new@example.com", "name": "New User"}
    )

    assert result == {"access_token": "access-token", "refresh_token": "refresh-token"}
    assign_mock.assert_not_called()


@pytest.mark.asyncio
async def test_login_or_create_user_no_longer_accepts_device_id():
    # device_id was removed along with the dead session store it fed;
    # this pins the simplified signature.
    import inspect

    sig = inspect.signature(oauth2_service.login_or_create_user)
    assert "device_id" not in sig.parameters


@pytest.mark.asyncio
async def test_login_or_create_user_normalizes_google_email_casing_for_lookup(mocker):
    # user_info is Google's raw JSON response : it never passes through a
    # Pydantic schema, so oauth2_service.py must normalize it itself before
    # ever calling get_by_email, unlike the signup/login paths.
    get_by_email_mock = mocker.patch(f"{MODULE}.user_crud.get_by_email", return_value=_FakeUser())
    mocker.patch(f"{MODULE}.jwt_service.create_access_token", return_value="access-token")
    mocker.patch(f"{MODULE}.jwt_service.create_refresh_token", return_value="refresh-token")
    mocker.patch(f"{MODULE}.redis_client.rpush", new_callable=AsyncMock)

    await oauth2_service.login_or_create_user(db=None, user_info={"email": "User@Example.COM"})

    get_by_email_mock.assert_awaited_once_with("user@example.com", None)


@pytest.mark.asyncio
async def test_login_or_create_user_normalizes_google_email_casing_for_new_account(mocker):
    mocker.patch(f"{MODULE}.user_crud.get_by_email", return_value=None)
    create_mock = mocker.patch(f"{MODULE}.user_crud.create", return_value=_FakeUser())
    mocker.patch(f"{MODULE}.policy_repository.get_by_name", return_value=_FakePolicy())
    mocker.patch(f"{MODULE}.policy_repository.assign_policy_to_user", new_callable=AsyncMock)
    mocker.patch(f"{MODULE}.jwt_service.create_access_token", return_value="access-token")
    mocker.patch(f"{MODULE}.jwt_service.create_refresh_token", return_value="refresh-token")

    await oauth2_service.login_or_create_user(
        db=None, user_info={"email": "New.User@Example.COM", "name": "New User"}
    )

    args, _ = create_mock.call_args
    assert args[0]["email"] == "new.user@example.com"
