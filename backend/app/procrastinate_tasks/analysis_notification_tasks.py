from sqlalchemy import select

from ..app_sdk import send_email_task
from ..balance_sheets.analysis_models import AnalysisAlert, AnalysisNotificationPolicy
from ..balance_sheets.analysis_notifications import (
    deliver_webhook,
    get_or_create_webhook_delivery,
    queue_alert_deliveries,
)
from ..sdk import database, procrastinate_app


@procrastinate_app.periodic(cron="*/15 * * * *")
@procrastinate_app.task
async def queue_analysis_alert_notifications(timestamp: int) -> int:
    """Queue email jobs and deliver an optional deployment webhook."""
    del timestamp
    queued = 0
    async with database.async_session() as session:
        result = await session.execute(
            select(AnalysisAlert, AnalysisNotificationPolicy)
            .join(AnalysisNotificationPolicy, AnalysisNotificationPolicy.company_id == AnalysisAlert.company_id)
            .where(AnalysisAlert.status == "open", AnalysisNotificationPolicy.enabled.is_(True))
        )
        for alert, policy in result.all():
            deliveries = await queue_alert_deliveries(alert, policy, session)
            for delivery in deliveries:
                delivery.job_id = await send_email_task.defer_async(
                    to_email=delivery.recipient,
                    subject=f"Financial review alert for company {alert.company_id}",
                    body=f"{alert.message}\n\nAffected periods: {', '.join(map(str, alert.years)) or 'not specified'}",
                    is_html=False,
                )
                queued += 1
            webhook_delivery = await get_or_create_webhook_delivery(alert, session)
            if webhook_delivery is not None and webhook_delivery.status in {"queued", "failed"}:
                if await deliver_webhook(alert):
                    webhook_delivery.status = "sent"
                    queued += 1
                else:
                    webhook_delivery.status = "failed"
            if deliveries or webhook_delivery is not None:
                await session.commit()
    return queued
