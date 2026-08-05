# tests/backend/mystic_auth/unit/test_signup_unit.py
from unittest.mock import AsyncMock

import pytest
from backend.mystic_auth.auth.signup.signup_handler import signup_handler
from backend.mystic_auth.auth.signup.signup_service import signup_service

HANDLER_MODULE = "backend.mystic_auth.auth.signup.signup_handler"
SERVICE_MODULE = "backend.mystic_auth.auth.signup.signup_service"


class _FakeUser:
    pass


# ---------------------------- handle_signup: enumeration resistance ----------------------------

@pytest.mark.asyncio
async def test_signup_missing_fields_returns_400(mocker):
    signup_mock = mocker.patch(f"{HANDLER_MODULE}.signup_service.signup")

    response = await signup_handler.handle_signup(name="", email="", password="", db=None)

    assert response.status_code == 400
    signup_mock.assert_not_called()


@pytest.mark.asyncio
async def test_signup_weak_password_returns_400_before_touching_signup_service(mocker):
    signup_mock = mocker.patch(f"{HANDLER_MODULE}.signup_service.signup")
    send_email_mock = mocker.patch(
        f"{HANDLER_MODULE}.account_verification_service.send_verification_email",
        new_callable=AsyncMock,
    )

    response = await signup_handler.handle_signup(
        name="New User", email="new@example.com", password="short", db=None
    )

    assert response.status_code == 400
    # A weak password must be rejected before any DB lookup/creation is
    # attempted, and this rejection is independent of email : checking it
    # first also keeps it from ever interacting with enumeration resistance.
    signup_mock.assert_not_called()
    send_email_mock.assert_not_called()


@pytest.mark.asyncio
async def test_signup_new_account_sends_verification_email_and_returns_generic_message(mocker):
    mocker.patch(f"{HANDLER_MODULE}.signup_service.signup", return_value=True)
    send_email_mock = mocker.patch(
        f"{HANDLER_MODULE}.account_verification_service.send_verification_email",
        new_callable=AsyncMock,
    )

    response = await signup_handler.handle_signup(
        name="New User", email="new@example.com", password="StrongPass123!", db=None
    )

    assert response.status_code == 200
    send_email_mock.assert_awaited_once_with("new@example.com")


@pytest.mark.asyncio
async def test_signup_duplicate_email_returns_identical_response_without_sending_email(mocker):
    mocker.patch(f"{HANDLER_MODULE}.signup_service.signup", return_value=False)
    send_email_mock = mocker.patch(
        f"{HANDLER_MODULE}.account_verification_service.send_verification_email",
        new_callable=AsyncMock,
    )

    new_response = await signup_handler.handle_signup(
        name="New User", email="new@example.com", password="StrongPass123!", db=None
    )
    dup_response = await signup_handler.handle_signup(
        name="Existing User", email="existing@example.com", password="StrongPass123!", db=None
    )

    # A duplicate-email signup attempt must be indistinguishable from a
    # successful one: same status code, same message body, and : unlike a
    # genuinely new signup : no verification email sent to the existing account.
    assert dup_response.status_code == new_response.status_code == 200
    assert dup_response.body == new_response.body
    send_email_mock.assert_not_called()


# ---------------------------- signup_service ----------------------------

@pytest.mark.asyncio
async def test_signup_service_rejects_duplicate_email_without_creating(mocker):
    mocker.patch(f"{SERVICE_MODULE}.user_crud.get_by_email", return_value=_FakeUser())
    create_mock = mocker.patch(f"{SERVICE_MODULE}.user_crud.create")

    result = await signup_service.signup(
        name="Existing User", email="existing@example.com", password="StrongPass123!", db=None
    )

    assert result is False
    create_mock.assert_not_called()


@pytest.mark.asyncio
async def test_signup_service_hashes_password_even_for_duplicate_email(mocker):
    # Regression guard for the signup timing side channel: skipping the
    # Argon2 hash on the duplicate-email path (while still hashing on the
    # new-email path) would let an attacker distinguish registered vs.
    # unregistered emails purely by response latency, even though
    # handle_signup returns an identical body/status for both.
    mocker.patch(f"{SERVICE_MODULE}.user_crud.get_by_email", return_value=_FakeUser())
    mocker.patch(f"{SERVICE_MODULE}.user_crud.create")
    hash_mock = mocker.patch(
        f"{SERVICE_MODULE}.password_service.hash_password", return_value="hashed-value"
    )

    result = await signup_service.signup(
        name="Existing User", email="existing@example.com", password="StrongPass123!", db=None
    )

    assert result is False
    hash_mock.assert_awaited_once_with("StrongPass123!")


class _FakeCreatedUser:
    def __init__(self, id=42):
        self.id = id


@pytest.mark.asyncio
async def test_signup_service_creates_new_unverified_user(mocker):
    mocker.patch(f"{SERVICE_MODULE}.user_crud.get_by_email", return_value=None)
    mocker.patch(f"{SERVICE_MODULE}.password_service.hash_password", return_value="hashed-value")
    create_mock = mocker.patch(
        f"{SERVICE_MODULE}.user_crud.create", new_callable=AsyncMock, return_value=_FakeCreatedUser()
    )
    mocker.patch(
        f"{SERVICE_MODULE}.policy_repository.get_by_name",
        new_callable=AsyncMock,
        return_value=mocker.Mock(id=1),
    )
    mocker.patch(f"{SERVICE_MODULE}.policy_repository.assign_policy_to_user", new_callable=AsyncMock)

    result = await signup_service.signup(
        name="New User", email="new@example.com", password="StrongPass123!", db=None
    )

    assert result is True
    create_mock.assert_awaited_once()
    args, _ = create_mock.call_args
    user_data = args[0]
    assert user_data["email"] == "new@example.com"
    assert user_data["hashed_password"] == "hashed-value"
    assert user_data["is_verified"] is False


@pytest.mark.asyncio
async def test_signup_service_assigns_self_service_policy_to_new_user(mocker):
    # PBAC regression guard: a new account's access must come from an
    # explicit default policy assignment, never from its (metadata-only)
    # role : see the role-as-metadata invariant.
    mocker.patch(f"{SERVICE_MODULE}.user_crud.get_by_email", return_value=None)
    mocker.patch(f"{SERVICE_MODULE}.password_service.hash_password", return_value="hashed-value")
    mocker.patch(
        f"{SERVICE_MODULE}.user_crud.create", new_callable=AsyncMock, return_value=_FakeCreatedUser(id=42)
    )
    get_by_name_mock = mocker.patch(
        f"{SERVICE_MODULE}.policy_repository.get_by_name",
        new_callable=AsyncMock,
        return_value=mocker.Mock(id=7),
    )
    assign_mock = mocker.patch(
        f"{SERVICE_MODULE}.policy_repository.assign_policy_to_user", new_callable=AsyncMock
    )

    result = await signup_service.signup(
        name="New User", email="new@example.com", password="StrongPass123!", db=None
    )

    assert result is True
    get_by_name_mock.assert_awaited_once_with("self_service", None)
    assign_mock.assert_awaited_once_with(user_id=42, policy_id=7, db=None, assigned_by="system")


@pytest.mark.asyncio
async def test_signup_service_still_succeeds_if_default_policy_is_missing(mocker):
    # An operational/migration issue (baseline policy not seeded) must not
    # take down signup entirely : it's logged loudly instead (see
    # signup_service.py), and the account can be fixed up by an admin later.
    mocker.patch(f"{SERVICE_MODULE}.user_crud.get_by_email", return_value=None)
    mocker.patch(f"{SERVICE_MODULE}.password_service.hash_password", return_value="hashed-value")
    mocker.patch(
        f"{SERVICE_MODULE}.user_crud.create", new_callable=AsyncMock, return_value=_FakeCreatedUser()
    )
    mocker.patch(
        f"{SERVICE_MODULE}.policy_repository.get_by_name", new_callable=AsyncMock, return_value=None
    )
    assign_mock = mocker.patch(
        f"{SERVICE_MODULE}.policy_repository.assign_policy_to_user", new_callable=AsyncMock
    )

    result = await signup_service.signup(
        name="New User", email="new@example.com", password="StrongPass123!", db=None
    )

    assert result is True
    assign_mock.assert_not_called()
