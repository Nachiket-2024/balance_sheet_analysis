"""Generic downstream account-lifecycle event delivery."""

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Literal

from sqlalchemy import select

from ..logging.logging_config import get_worker_logger

logger = get_worker_logger(__name__)

AccountLifecycleEventType = Literal["soft_deleted", "reactivated", "purged"]


@dataclass(frozen=True)
class AccountLifecycleEvent:
    """Metadata for downstream cleanup or reconciliation.

    This contains identifiers and state-transition metadata only. It never
    contains passwords, tokens, integration secrets, or request bodies.
    """

    event_type: AccountLifecycleEventType
    user_id: int | None
    user_email: str
    actor: str
    source: str
    occurred_at: datetime

    def as_payload(self) -> dict:
        payload = asdict(self)
        payload["occurred_at"] = self.occurred_at.isoformat()
        return payload

    @classmethod
    def from_payload(cls, payload: dict) -> AccountLifecycleEvent:
        return cls(**{**payload, "occurred_at": datetime.fromisoformat(payload["occurred_at"])})


async def deliver_account_lifecycle_event(event: AccountLifecycleEvent) -> None:
    """Call registered downstream listeners in the worker process.

    Listener failures are logged and re-raised so Procrastinate retries the
    event. Listeners must be idempotent because a retry can repeat delivery.
    """
    from .account_lifecycle_registry import notify_account_lifecycle_listeners

    await notify_account_lifecycle_listeners(event)


def build_account_lifecycle_event(
    event_type: AccountLifecycleEventType,
    user,
    *,
    actor: str,
    source: str,
) -> AccountLifecycleEvent:
    return AccountLifecycleEvent(
        event_type=event_type,
        user_id=getattr(user, "id", None),
        user_email=user.email,
        actor=actor,
        source=source,
        occurred_at=datetime.now(UTC),
    )


async def mark_account_lifecycle_event_delivered(outbox_id: int) -> None:
    from ..database.connection import database
    from .account_lifecycle_outbox_model import AccountLifecycleOutbox

    async with database.async_session() as session:
        outbox = await session.get(AccountLifecycleOutbox, outbox_id)
        if outbox is not None and outbox.delivered_at is None:
            outbox.delivered_at = datetime.now(UTC)
            await session.commit()


async def queue_account_lifecycle_event(event: AccountLifecycleEvent, *, outbox_id: int | None = None) -> int | None:
    """Queue an event without blocking the account state transition.

    The account mutation and outbox row are committed together. If the worker
    queue is unavailable, the periodic reconciler will retry unqueued rows.

    When `outbox_id` is given, the row is claimed with `SELECT ... FOR UPDATE
    SKIP LOCKED WHERE queued_at IS NULL` before deferring the job, and
    `queued_at` is only set after `defer_async` actually succeeds, all inside
    one transaction held across the defer call. This is what makes two
    concurrent callers for the same row (the original caller right after
    insert, and the periodic reconciler picking up the same row because the
    first call hadn't committed `queued_at` yet) produce exactly one deferred
    job instead of two: the second caller's SELECT returns no row (it's
    either already locked by the first caller, or already has `queued_at`
    set) and skips deferring entirely, rather than racing to defer and then
    both writing `queued_at` after the fact.
    """
    from ..procrastinate_tasks.account_lifecycle_tasks import deliver_account_lifecycle_event_task

    if outbox_id is None:
        try:
            return await deliver_account_lifecycle_event_task.defer_async(event=event.as_payload(), outbox_id=None)
        except Exception:
            logger.critical(
                "Could not queue account lifecycle event %s for user %s",
                event.event_type,
                event.user_email,
                exc_info=True,
            )
            return None

    from ..database.connection import database
    from .account_lifecycle_outbox_model import AccountLifecycleOutbox

    try:
        async with database.async_session() as session:
            result = await session.execute(
                select(AccountLifecycleOutbox)
                .where(AccountLifecycleOutbox.id == outbox_id, AccountLifecycleOutbox.queued_at.is_(None))
                .with_for_update(skip_locked=True)
            )
            outbox = result.scalar_one_or_none()
            if outbox is None:
                # Already queued, already claimed by a concurrent caller, or
                # no longer exists. Nothing to do: whichever caller actually
                # holds the claim is responsible for deferring the job.
                return None

            job_id = await deliver_account_lifecycle_event_task.defer_async(
                event=event.as_payload(), outbox_id=outbox_id
            )
            outbox.queued_at = datetime.now(UTC)
            await session.commit()
            return job_id
    except Exception:
        logger.critical(
            "Could not queue account lifecycle event %s for user %s",
            event.event_type,
            event.user_email,
            exc_info=True,
        )
        return None
