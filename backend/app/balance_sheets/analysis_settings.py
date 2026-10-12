from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .analysis_models import AnalysisAlert, CompanyAnalysisSettings
from .analysis_schema import AnalysisWarning
from .analysis_service import THRESHOLDS


def validate_thresholds(values: dict[str, float]) -> dict[str, float]:
    unknown = set(values) - set(THRESHOLDS)
    if unknown:
        raise ValueError(f"Unknown threshold(s): {', '.join(sorted(unknown))}")
    normalized = {key: float(value) for key, value in values.items()}
    if any(value < 0 for value in normalized.values()):
        raise ValueError("Thresholds must be non-negative")
    return normalized


async def get_or_create_settings(company_id: int, db: AsyncSession) -> CompanyAnalysisSettings:
    result = await db.execute(select(CompanyAnalysisSettings).where(CompanyAnalysisSettings.company_id == company_id))
    settings = result.scalar_one_or_none()
    if settings is None:
        settings = CompanyAnalysisSettings(company_id=company_id, thresholds={})
        db.add(settings)
        await db.commit()
        await db.refresh(settings)
    return settings


def effective_thresholds(settings: CompanyAnalysisSettings | None) -> dict[str, float | int]:
    return {**THRESHOLDS, **(settings.thresholds if settings else {})}


async def sync_analysis_alerts(company_id: int, warnings: list[AnalysisWarning], db: AsyncSession) -> None:
    now = datetime.now(UTC)
    active_keys: set[str] = set()
    for warning in warnings:
        key = f"{warning.type}:{','.join(map(str, warning.years))}"
        active_keys.add(key)
        result = await db.execute(select(AnalysisAlert).where(AnalysisAlert.company_id == company_id, AnalysisAlert.alert_key == key))
        alert = result.scalar_one_or_none()
        if alert is None:
            db.add(AnalysisAlert(company_id=company_id, alert_key=key, alert_type=warning.type, severity=warning.severity, message=warning.message, years=warning.years, evidence=warning.evidence, last_seen_at=now))
        else:
            alert.message = warning.message
            alert.years = warning.years
            alert.evidence = warning.evidence
            alert.last_seen_at = now
            if alert.status == "resolved":
                alert.status = "open"
    existing = await db.execute(select(AnalysisAlert).where(AnalysisAlert.company_id == company_id, AnalysisAlert.status == "open"))
    for alert in existing.scalars():
        if alert.alert_key not in active_keys:
            alert.status = "resolved"
    await db.commit()
