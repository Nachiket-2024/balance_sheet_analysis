# tests/backend/mystic_auth/unit/database/test_base_unit.py
#
# Base is the shared SQLAlchemy declarative base every ORM model inherits
# from. These tests guard that it stays a 2.0-style DeclarativeBase with
# AsyncAttrs mixed in (needed for Mapped[...]/mapped_column() to type-check,
# see Base's own docstring) instead of regressing to the legacy
# declarative_base() factory.
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from backend.mystic_auth.database.base import Base


def test_base_is_a_declarative_base():
    assert issubclass(Base, DeclarativeBase)


def test_base_mixes_in_async_attrs():
    assert issubclass(Base, AsyncAttrs)


def test_a_model_inheriting_base_maps_correctly():
    # Round-trips the exact style used by the real models (Mapped[...] +
    # mapped_column()). If Base ever regressed to the legacy
    # declarative_base() factory, this class definition itself would fail.
    class _ExampleModel(Base):
        __tablename__ = "_example_model_for_base_unit_test"

        id: Mapped[int] = mapped_column(primary_key=True)

    assert "_example_model_for_base_unit_test" in Base.metadata.tables
    instance = _ExampleModel(id=1)
    assert instance.id == 1
