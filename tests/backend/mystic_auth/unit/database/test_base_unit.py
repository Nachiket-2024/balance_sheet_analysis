# tests/backend/mystic_auth/unit/database/test_base_unit.py
#
# Base is the shared SQLAlchemy declarative base every ORM model in
# mystic_auth/*/models*.py inherits from; this guards it stays a
# 2.0-style DeclarativeBase with AsyncAttrs mixed in (required for the
# Mapped[...]/mapped_column() model style to type-check under the
# SQLAlchemy mypy plugin, see Base's own docstring), rather than silently
# regressing to the legacy declarative_base() factory.
from backend.mystic_auth.database.base import Base
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def test_base_is_a_declarative_base():
    assert issubclass(Base, DeclarativeBase)


def test_base_mixes_in_async_attrs():
    assert issubclass(Base, AsyncAttrs)


def test_a_model_inheriting_base_maps_correctly():
    # Round-trips the exact style used throughout the real models
    # (Mapped[...] + mapped_column()): if Base ever regressed to the legacy
    # declarative_base() factory, this class definition itself would fail
    # to type-check/construct correctly.
    class _ExampleModel(Base):
        __tablename__ = "_example_model_for_base_unit_test"

        id: Mapped[int] = mapped_column(primary_key=True)

    assert "_example_model_for_base_unit_test" in Base.metadata.tables
    instance = _ExampleModel(id=1)
    assert instance.id == 1
