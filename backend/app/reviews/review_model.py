from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from ..app_sdk import Base


class ReviewReport(Base):
    """A point-in-time, deterministic analysis artifact for management review."""

    __tablename__ = "review_reports"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    created_by_email: Mapped[str] = mapped_column(String(320), index=True)
    title: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(32), index=True, default="draft", server_default="draft")
    years: Mapped[list[int]] = mapped_column(JSON)
    analysis: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class ReviewComment(Base):
    __tablename__ = "review_comments"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    review_report_id: Mapped[int] = mapped_column(ForeignKey("review_reports.id", ondelete="CASCADE"), index=True)
    author_email: Mapped[str] = mapped_column(String(320), index=True)
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ReviewAssignment(Base):
    __tablename__ = "review_assignments"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    review_report_id: Mapped[int] = mapped_column(ForeignKey("review_reports.id", ondelete="CASCADE"), index=True)
    assigned_to_email: Mapped[str] = mapped_column(String(320), index=True)
    assigned_by_email: Mapped[str] = mapped_column(String(320), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ReviewSignoff(Base):
    __tablename__ = "review_signoffs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    review_report_id: Mapped[int] = mapped_column(ForeignKey("review_reports.id", ondelete="CASCADE"), index=True)
    actor_email: Mapped[str] = mapped_column(String(320), index=True)
    status: Mapped[str] = mapped_column(String(32))
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
