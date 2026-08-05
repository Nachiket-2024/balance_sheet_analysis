from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from ..app_sdk import Base


class Company(Base):
    """
    A company or business vertical (e.g. "Reliance Industries", with
    "Jio Platforms"/"Reliance Retail Ventures" as children). Self-referential
    via parent_company_id, which alone models the problem statement's
    "Reliance has multiple verticals" hierarchy, so there is no separate
    Vertical concept (the old repo's unused Vertical model was dropped; a
    vertical is just an ordinary child Company row).

    group_root_id is the denormalized top-most ancestor's id (equal to this
    row's own id for a root company). It exists purely so PBAC policies can
    grant "every company in this group" as a single flat equality condition
    (see app/access/scope.py's module docstring), since mystic-auth's
    resource_attributes condition only supports flat equality, not walking
    parent_company_id recursively at authorization time.
    """

    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    name: Mapped[str] = mapped_column(String, index=True)
    # The public-market ticker (e.g. "RELIANCE.NS"), a real FK target for
    # BalanceSheet.company_id below, replacing the old repo's unenforced
    # `ticker == Company.name` string join.
    ticker: Mapped[str] = mapped_column(String, unique=True, index=True)

    parent_company_id: Mapped[int | None] = mapped_column(
        ForeignKey("companies.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # Maintained by company_crud.py on create/update, never set directly by
    # a route/request body. See class docstring for why this exists.
    group_root_id: Mapped[int] = mapped_column(index=True)

    # Explicit DateTime(timezone=True), matching mystic_auth's own User model
    # convention; SQLAlchemy's default `Mapped[datetime]` mapping is naive
    # DateTime() otherwise, which drifted from the migration's
    # TIMESTAMP(timezone=True) column and failed `alembic check` in CI.
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    parent_company: Mapped[Company | None] = relationship(remote_side=[id], back_populates="subsidiaries")
    subsidiaries: Mapped[list[Company]] = relationship(back_populates="parent_company")
