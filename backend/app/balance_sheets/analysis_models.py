from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from ..app_sdk import Base


class CompanyAnalysisSettings(Base):
    __tablename__ = "company_analysis_settings"
    __table_args__ = (UniqueConstraint("company_id"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    thresholds: Mapped[dict[str, float]] = mapped_column(JSON, default=dict, server_default=text("'{}'"))
    target_currency: Mapped[str | None] = mapped_column(String(8), nullable=True)
    display_scale: Mapped[float] = mapped_column(default=1.0, server_default="1")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class AnalysisSettingsHistory(Base):
    __tablename__ = "analysis_settings_history"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    changed_by: Mapped[str] = mapped_column(String(320), index=True)
    thresholds: Mapped[dict[str, float]] = mapped_column(JSON)
    target_currency: Mapped[str | None] = mapped_column(String(8), nullable=True)
    display_scale: Mapped[float] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AnalysisAlert(Base):
    __tablename__ = "analysis_alerts"
    __table_args__ = (UniqueConstraint("company_id", "alert_key", name="uq_analysis_alert_company_key"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    alert_key: Mapped[str] = mapped_column(String(255))
    alert_type: Mapped[str] = mapped_column(String(64), index=True)
    severity: Mapped[str] = mapped_column(String(32), index=True)
    message: Mapped[str] = mapped_column(Text)
    years: Mapped[list[int]] = mapped_column(JSON, default=list)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(32), default="open", server_default="open", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    acknowledged_by: Mapped[str | None] = mapped_column(String(320), nullable=True)


class AnalysisNotificationPolicy(Base):
    __tablename__ = "analysis_notification_policies"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), unique=True)
    enabled: Mapped[bool] = mapped_column(default=False, server_default="false")
    recipients: Mapped[list[str]] = mapped_column(JSON, default=list)
    minimum_severity: Mapped[str] = mapped_column(String(32), default="review", server_default="review")
    escalation_after_hours: Mapped[int] = mapped_column(default=0, server_default="0")
    escalation_recipients: Mapped[list[str]] = mapped_column(JSON, default=list)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class AnalysisNotificationPreference(Base):
    __tablename__ = "analysis_notification_preferences"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_email: Mapped[str] = mapped_column(String(320), unique=True)
    email_enabled: Mapped[bool] = mapped_column(default=True, server_default="true")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class AnalysisNotificationDelivery(Base):
    __tablename__ = "analysis_notification_deliveries"
    __table_args__ = (UniqueConstraint("alert_id", "recipient", name="uq_analysis_notification_delivery_recipient"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    alert_id: Mapped[int] = mapped_column(ForeignKey("analysis_alerts.id", ondelete="CASCADE"), index=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    channel: Mapped[str] = mapped_column(String(32), default="email", server_default="email", index=True)
    recipient: Mapped[str] = mapped_column(String(320), index=True)
    status: Mapped[str] = mapped_column(String(32), default="queued", server_default="queued", index=True)
    job_id: Mapped[int | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
