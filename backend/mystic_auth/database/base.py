from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase


class Base(AsyncAttrs, DeclarativeBase):
    """SQLAlchemy 2.0-style declarative base (not the legacy
    `declarative_base()` factory). Needed so the `Mapped[...]`/
    `mapped_column()` model style used throughout the codebase type-checks
    with the SQLAlchemy mypy plugin, which doesn't recognize the legacy
    factory's generated `__init__` and would reject calls like
    `Policy(name=..., actions=...)`.
    """

