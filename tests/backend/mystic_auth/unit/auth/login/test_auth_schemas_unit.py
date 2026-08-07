# tests/backend/mystic_auth/unit/test_auth_schemas_unit.py
#
# Regression guard: name/password/token fields across the auth request
# schemas previously accepted unbounded-length strings, which then get fed
# straight into Argon2 hashing (password/name) or Redis/JWT operations
# (tokens). These are pure schema-level unit tests since handlers take
# plain str arguments and bypass FastAPI's request-parsing/validation layer
# entirely : only a Pydantic model instantiation (or a real HTTP request,
# covered separately in integration tests) actually exercises these limits.
import pytest
from backend.mystic_auth.auth.login.login_schema import LoginSchema
from backend.mystic_auth.auth.password_reset_confirm.password_reset_confirm_schema import (
    PasswordResetConfirmSchema,
)
from backend.mystic_auth.auth.password_reset_request.password_reset_request_schema import (
    PasswordResetRequestSchema,
)
from backend.mystic_auth.auth.signup.signup_schema import SignupSchema
from backend.mystic_auth.auth.verify_account.verify_account_schema import (
    VerifyAccountSchema,
)
from backend.mystic_auth.user_table.user_schema import UserCreate, UserUpdate
from pydantic import ValidationError


def test_signup_rejects_name_over_max_length():
    with pytest.raises(ValidationError):
        SignupSchema(name="a" * 101, email="user@example.com", password="ValidPass123!")


def test_signup_accepts_name_at_max_length():
    schema = SignupSchema(name="a" * 100, email="user@example.com", password="ValidPass123!")
    assert len(schema.name) == 100


def test_signup_rejects_password_over_max_length():
    with pytest.raises(ValidationError):
        SignupSchema(name="Test User", email="user@example.com", password="a" * 129)


def test_signup_accepts_password_at_max_length():
    schema = SignupSchema(name="Test User", email="user@example.com", password="a" * 128)
    assert len(schema.password) == 128


def test_login_rejects_password_over_max_length():
    with pytest.raises(ValidationError):
        LoginSchema(email="user@example.com", password="a" * 129)


def test_login_accepts_password_at_max_length():
    schema = LoginSchema(email="user@example.com", password="a" * 128)
    assert len(schema.password) == 128


def test_password_reset_confirm_rejects_token_over_max_length():
    with pytest.raises(ValidationError):
        PasswordResetConfirmSchema(token="a" * 2049, new_password="ValidPass123!")


def test_password_reset_confirm_rejects_new_password_over_max_length():
    with pytest.raises(ValidationError):
        PasswordResetConfirmSchema(token="valid-token", new_password="a" * 129)


def test_password_reset_confirm_accepts_values_at_max_length():
    schema = PasswordResetConfirmSchema(token="a" * 2048, new_password="a" * 128)
    assert len(schema.token) == 2048
    assert len(schema.new_password) == 128


def test_verify_account_schema_rejects_token_over_max_length():
    with pytest.raises(ValidationError):
        VerifyAccountSchema(token="a" * 2049)


def test_verify_account_schema_accepts_token_at_max_length():
    schema = VerifyAccountSchema(token="a" * 2048)
    assert len(schema.token) == 2048


# ---------------------------- Email casing normalization ----------------------------
#
# Regression guard: `User@Example.com` and `user@example.com` must be treated
# as the same account. These schemas are the input boundary for signup,
# login, and password-reset-request : normalizing here (in addition to the
# CRUD-layer normalization in UserEmailCRUD) means the canonical lowercase
# form flows through logs/tokens/audit from the earliest point.

def test_signup_schema_lowercases_mixed_case_email():
    schema = SignupSchema(name="Test User", email="User@Example.COM", password="ValidPass123!")
    assert schema.email == "user@example.com"


def test_login_schema_lowercases_mixed_case_email():
    schema = LoginSchema(email="User@Example.COM", password="ValidPass123!")
    assert schema.email == "user@example.com"


def test_password_reset_request_schema_lowercases_mixed_case_email():
    schema = PasswordResetRequestSchema(email="User@Example.COM")
    assert schema.email == "user@example.com"


# ---------------------------- UserUpdate/UserCreate length caps ----------------------------
#
# Regression guard: these schemas back PUT /users/me and PUT /users/{email}
# (self and admin password/profile changes) and previously had no
# max_length at all on name/password, unlike signup_schema.SignupSchema :
# an unbounded password fed straight into Argon2 hashing is exactly the DoS
# vector the signup cap exists to prevent.

def test_user_update_rejects_password_over_max_length():
    with pytest.raises(ValidationError):
        UserUpdate(password="a" * 129)


def test_user_update_accepts_password_at_max_length():
    schema = UserUpdate(password="a" * 128)
    assert len(schema.password) == 128


def test_user_update_rejects_name_over_max_length():
    with pytest.raises(ValidationError):
        UserUpdate(name="a" * 101)


def test_user_update_accepts_name_at_max_length():
    schema = UserUpdate(name="a" * 100)
    assert len(schema.name) == 100


def test_user_create_rejects_password_over_max_length():
    with pytest.raises(ValidationError):
        UserCreate(name="Test User", email="user@example.com", password="a" * 129)


def test_user_create_rejects_name_over_max_length():
    with pytest.raises(ValidationError):
        UserCreate(name="a" * 101, email="user@example.com", password="ValidPass123!")
