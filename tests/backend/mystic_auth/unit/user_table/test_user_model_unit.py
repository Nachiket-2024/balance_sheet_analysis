# tests/backend/mystic_auth/unit/user_table/test_user_model_unit.py
#
# Guards the ORM shape (table name, columns, role enum) directly, rather
# than only ever exercising User through CRUD/route tests that happen to
# touch it indirectly.
from backend.mystic_auth.database.base import Base
from backend.mystic_auth.user_table.user_model import User, UserRole


def test_user_role_enum_has_the_three_documented_roles():
    assert {r.value for r in UserRole} == {"user", "admin", "system"}


def test_user_table_name_is_users():
    assert User.__tablename__ == "users"


def test_user_is_declarative_base_subclass():
    assert issubclass(User, Base)


def test_user_role_column_is_nullable():
    # Role is display/grouping metadata only (see authorization/ for the
    # real PBAC decision-maker): the model must support a roleless account
    # authorized purely through assigned policies.
    assert User.__table__.columns["role"].nullable is True


def test_user_email_column_is_unique_and_indexed():
    email_column = User.__table__.columns["email"]

    assert email_column.unique is True
    assert email_column.index is True


def test_user_defaults_to_unverified_and_active():
    assert User.__table__.columns["is_verified"].default.arg is False
    assert User.__table__.columns["is_active"].default.arg is True
