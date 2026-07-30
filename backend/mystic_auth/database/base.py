from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase


class Base(AsyncAttrs, DeclarativeBase):
    """
    SQLAlchemy 2.0-style declarative base (not the legacy `declarative_base()`
    factory), required for the `Mapped[...]`/`mapped_column()` model style
    used throughout `mystic_auth/*/models*.py` to type-check correctly with
    the SQLAlchemy mypy plugin; the legacy factory's generated `__init__`
    isn't recognized by the plugin, which otherwise rejects legitimate
    keyword-constructor calls like `Policy(name=..., actions=...)`.
    """

