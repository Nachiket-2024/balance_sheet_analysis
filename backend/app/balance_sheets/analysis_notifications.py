from collections.abc import Iterable
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .analysis_models import (
    AnalysisAlert,
    AnalysisNotificationDelivery,
    AnalysisNotificationPolicy,
    AnalysisNotificationPreference,
)
from .notification_config import ANALYSIS_ALERT_WEBHOOK_URL

SEVERITY_ORDER = {"info": 0, "review": 1}


def normalize_recipients(recipients: Iterable[str]) -> list[str]:
    return sorted({recipient.strip().lower() for recipient in recipients if recipient.strip()})


def validate_policy(
    *, recipients: list[str], minimum_severity: str, escalation_after_hours: int, escalation_recipients: list[str]
) -> dict:
    if minimum_severity not in SEVERITY_ORDER:
        raise ValueError("minimum_severity must be info or review")
    if escalation_after_hours < 0 or escalation_after_hours > 30 * 24:
        raise ValueError("escalation_after_hours must be between 0 and 720")
    all_recipients = [*recipients, *escalation_recipients]
    if any("@" not in recipient or recipient.startswith("@") or recipient.endswith("@") for recipient in all_recipients):
        raise ValueError("Notification recipients must be email addresses")
    return {
        "recipients": normalize_recipients(recipients),
        "minimum_severity": minimum_severity,
        "escalation_after_hours": escalation_after_hours,
        "escalation_recipients": normalize_recipients(escalation_recipients),
    }


async def get_or_create_policy(company_id: int, db: AsyncSession) -> AnalysisNotificationPolicy:
    result = await db.execute(select(AnalysisNotificationPolicy).where(AnalysisNotificationPolicy.company_id == company_id))
    policy = result.scalar_one_or_none()
    if policy is None:
        policy = AnalysisNotificationPolicy(company_id=company_id, recipients=[], escalation_recipients=[])
        db.add(policy)
        await db.commit()
        await db.refresh(policy)
    return policy


async def get_or_create_preference(user_email: str, db: AsyncSession) -> AnalysisNotificationPreference:
    result = await db.execute(select(AnalysisNotificationPreference).where(AnalysisNotificationPreference.user_email == user_email))
    preference = result.scalar_one_or_none()
    if preference is None:
        preference = AnalysisNotificationPreference(user_email=user_email)
        db.add(preference)
        await db.commit()
        await db.refresh(preference)
    return preference


def notification_recipients(alert: AnalysisAlert, policy: AnalysisNotificationPolicy, now: datetime) -> list[str]:
    if not policy.enabled or SEVERITY_ORDER.get(alert.severity, 0) < SEVERITY_ORDER[policy.minimum_severity]:
        return []
    recipients = set(normalize_recipients(policy.recipients))
    if policy.escalation_after_hours and alert.created_at and now - alert.created_at >= timedelta(hours=policy.escalation_after_hours):
        recipients.update(normalize_recipients(policy.escalation_recipients))
    return sorted(recipients)


async def queue_alert_deliveries(
    alert: AnalysisAlert, policy: AnalysisNotificationPolicy, db: AsyncSession
) -> list[AnalysisNotificationDelivery]:
    recipients = notification_recipients(alert, policy, datetime.now(UTC))
    if not recipients:
        return []
    existing = await db.execute(select(AnalysisNotificationDelivery).where(AnalysisNotificationDelivery.alert_id == alert.id))
    existing_by_recipient = {delivery.recipient: delivery for delivery in existing.scalars()}
    preferences = await db.execute(select(AnalysisNotificationPreference).where(AnalysisNotificationPreference.user_email.in_(recipients)))
    opted_out = {preference.user_email for preference in preferences.scalars() if not preference.email_enabled}
    queued = []
    for recipient in recipients:
        if recipient in opted_out or recipient in existing_by_recipient:
            continue
        delivery = AnalysisNotificationDelivery(alert_id=alert.id, company_id=alert.company_id, recipient=recipient)
        db.add(delivery)
        queued.append(delivery)
    if queued:
        await db.flush()
    return queued


async def get_or_create_webhook_delivery(alert: AnalysisAlert, db: AsyncSession) -> AnalysisNotificationDelivery | None:
    """Create one deployment-webhook delivery without persisting its secret URL."""
    if not ANALYSIS_ALERT_WEBHOOK_URL:
        return None
    result = await db.execute(
        select(AnalysisNotificationDelivery).where(
            AnalysisNotificationDelivery.alert_id == alert.id,
            AnalysisNotificationDelivery.channel == "webhook",
        )
    )
    delivery = result.scalar_one_or_none()
    if delivery is None:
        delivery = AnalysisNotificationDelivery(
            alert_id=alert.id,
            company_id=alert.company_id,
            channel="webhook",
            recipient="configured-webhook",
        )
        db.add(delivery)
        await db.flush()
    return delivery


def webhook_payload(alert: AnalysisAlert) -> dict:
    return {
        "event": "analysis.alert",
        "company_id": alert.company_id,
        "alert_type": alert.alert_type,
        "severity": alert.severity,
        "message": alert.message,
        "years": alert.years,
        "evidence": alert.evidence,
    }


async def deliver_webhook(alert: AnalysisAlert) -> bool:
    if not ANALYSIS_ALERT_WEBHOOK_URL:
        return False
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=False) as client:
            response = await client.post(ANALYSIS_ALERT_WEBHOOK_URL, json=webhook_payload(alert))
            response.raise_for_status()
    except httpx.HTTPError:
        return False
    return True
