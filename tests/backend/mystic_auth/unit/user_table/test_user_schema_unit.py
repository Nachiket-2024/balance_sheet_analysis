# tests/backend/mystic_auth/unit/user_table/test_user_schema_unit.py
#
# UserRead/UserCreate/UserUpdate had no direct test coverage: everything
# about them (email normalization, password length caps, has_password
# derivation) was only exercised indirectly through route/CRUD tests.
import pytest
from backend.mystic_auth.user_table.user_model import UserRole
from backend.mystic_auth.user_table.user_schema import (
    UserCreate,
    UserRead,
    UserRoleUpdate,
    UserStatsRead,
    UserUpdate,
)
from pydantic import ValidationError


def test_user_create_normalizes_email_casing():
    user = UserCreate(name="Test User", email="User@Example.com", password="hunter2")

    assert user.email == "user@example.com"


def test_user_create_rejects_password_over_max_length():
    with pytest.raises(ValidationError):
        UserCreate(name="Test User", email="user@example.com", password="a" * 129)


def test_user_create_rejects_name_over_max_length():
    with pytest.raises(ValidationError):
        UserCreate(name="a" * 101, email="user@example.com", password="hunter2")


def test_user_create_rejects_whitespace_only_name():
    with pytest.raises(ValidationError):
        UserCreate(name="   ", email="user@example.com", password="hunter2")


def test_user_create_strips_surrounding_whitespace_from_name():
    user = UserCreate(name="  Test User  ", email="user@example.com", password="hunter2")

    assert user.name == "Test User"


def test_user_update_allows_all_fields_omitted():
    update = UserUpdate()

    assert update.name is None
    assert update.password is None
    assert update.current_password is None


def test_user_update_rejects_password_over_max_length():
    with pytest.raises(ValidationError):
        UserUpdate(password="a" * 129)


def test_user_update_rejects_whitespace_only_name():
    with pytest.raises(ValidationError):
        UserUpdate(name="   ")


def test_user_read_has_password_true_when_hash_present():
    user = UserRead(
        id=1,
        name="Test User",
        email="user@example.com",
        role=UserRole.user,
        is_verified=True,
        is_active=True,
        created_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
        hashed_password="$argon2id$fake-hash",
    )

    assert user.has_password is True


def test_user_read_has_password_false_for_oauth_only_account():
    user = UserRead(
        id=1,
        name="Test User",
        email="user@example.com",
        role=None,
        is_verified=True,
        is_active=True,
        created_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
        hashed_password=None,
    )

    assert user.has_password is False


def test_user_read_never_serializes_hashed_password():
    user = UserRead(
        id=1,
        name="Test User",
        email="user@example.com",
        role=UserRole.admin,
        is_verified=True,
        is_active=True,
        created_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
        hashed_password="$argon2id$fake-hash",
    )

    dumped = user.model_dump()

    assert "hashed_password" not in dumped
    assert dumped["has_password"] is True


def test_user_role_update_accepts_only_declared_roles():
    with pytest.raises(ValidationError):
        UserRoleUpdate(role="not-a-real-role")


def test_user_stats_read_holds_plain_counts():
    stats = UserStatsRead(total=10, verified=7, unverified=3, inactive=1)

    assert (stats.total, stats.verified, stats.unverified, stats.inactive) == (10, 7, 3, 1)
