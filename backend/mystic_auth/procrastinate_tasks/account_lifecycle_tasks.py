from typing import cast

from sqlalchemy import select

from ..database.connection import database
from ..logging.logging_config import get_worker_logger
from ..user_lifecycle.account_lifecycle_events import (
    AccountLifecycleEvent,
    AccountLifecycleEventType,
    deliver_account_lifecycle_event,
    mark_account_lifecycle_event_delivered,
    queue_account_lifecycle_event,
)
from ..user_lifecycle.account_lifecycle_outbox_model import AccountLifecycleOutbox
from .procrastinate_app import ExponentialBackoffWithJitter, app

logger = get_worker_logger(__name__)

ACCOUNT_LIFECYCLE_RETRY = ExponentialBackoffWithJitter(max_attempts=5, base_delay=5, max_delay=300, jitter=5)


@app.task(
    name="mystic_auth.procrastinate_tasks.account_lifecycle_tasks.deliver_account_lifecycle_event",
    retry=ACCOUNT_LIFECYCLE_RETRY,
)
async def deliver_account_lifecycle_event_task(event: dict, outbox_id: int | None = None) -> None:
    """Deliver one account transition to downstream listeners with retries."""
    logger.info("Delivering account lifecycle event %s", event.get("event_type"))
    await deliver_account_lifecycle_event(AccountLifecycleEvent.from_payload(event))
    if outbox_id is not None:
        await mark_account_lifecycle_event_delivered(outbox_id)


@app.periodic(cron="*/5 * * * *")
@app.task
async def dispatch_pending_account_lifecycle_events(timestamp: int) -> int:
    """Re-enqueue outbox rows whose initial queue submission failed."""
    async with database.async_session() as session:
        result = await session.execute(
            select(AccountLifecycleOutbox)
            .where(AccountLifecycleOutbox.queued_at.is_(None), AccountLifecycleOutbox.delivered_at.is_(None))
            .order_by(AccountLifecycleOutbox.id)
            .limit(100)
        )
        rows = result.scalars().all()

    queued = 0
    for row in rows:
        event = AccountLifecycleEvent(
            event_type=cast(AccountLifecycleEventType, row.event_type),
            user_id=row.user_id,
            user_email=row.user_email,
            actor=row.actor,
            source=row.source,
            occurred_at=row.occurred_at,
        )
        if await queue_account_lifecycle_event(event, outbox_id=row.id) is not None:
            queued += 1
    return queued
