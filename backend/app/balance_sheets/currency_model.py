from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from ..app_sdk import Base


class CurrencyRate(Base):
    __tablename__ = "currency_rates"
    __table_args__ = (UniqueConstraint("company_id", "source_currency", "target_currency", "effective_date", name="uq_currency_rate_period"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    source_currency: Mapped[str] = mapped_column(String(8), index=True)
    target_currency: Mapped[str] = mapped_column(String(8), index=True)
    effective_date: Mapped[date] = mapped_column(Date, index=True)
    rate: Mapped[float] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(128))
    source_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
