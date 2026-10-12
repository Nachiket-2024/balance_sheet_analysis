from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from ..app_sdk import Base


class LLMFeedback(Base):
    __tablename__ = "llm_feedback"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    user_email: Mapped[str] = mapped_column(String(320), index=True)
    helpful: Mapped[bool]
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class LLMUsage(Base):
    __tablename__ = "llm_usage"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_email: Mapped[str] = mapped_column(String(320), index=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str] = mapped_column(String(64))
    model: Mapped[str] = mapped_column(String(128))
    input_chars: Mapped[int] = mapped_column(default=0, server_default="0")
    output_chars: Mapped[int] = mapped_column(default=0, server_default="0")
    max_tokens: Mapped[int] = mapped_column(default=0, server_default="0")
    status: Mapped[str] = mapped_column(String(32), index=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class LLMProviderProbe(Base):
    """Bounded provider health history used by the operations summary."""

    __tablename__ = "llm_provider_probes"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    provider: Mapped[str] = mapped_column(String(64), index=True)
    model: Mapped[str] = mapped_column(String(128))
    reachable: Mapped[bool]
    latency_ms: Mapped[float | None] = mapped_column(nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
