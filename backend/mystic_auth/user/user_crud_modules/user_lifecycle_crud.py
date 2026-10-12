from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from ...user_lifecycle.account_lifecycle_events import AccountLifecycleEvent
from ...user_lifecycle.account_lifecycle_outbox_model import AccountLifecycleOutbox


class UserLifecycleCRUD:
    """
    Account-lifecycle-specific CRUD operations for the users table.

    Kept separate from UserBaseCRUD.update: both operations touch exactly two
    columns (is_active, deleted_at) with app-computed values, not
    caller-supplied ones, so they shouldn't go through the generic "update
    with an arbitrary dict" entry point a profile edit uses. That dict would
    let a caller set deleted_at to anything.
    """

    def __init__(self, model):
        self.model = model

    async def soft_delete(self, db_obj, db: AsyncSession, lifecycle_event: AccountLifecycleEvent | None = None):
        """Sets is_active=False (the flag login_service.py, oauth2_service.py,
        and current_user_handler.py already gate on) and deleted_at=now."""
        if not db_obj:
            return None

        db_obj.is_active = False
        db_obj.deleted_at = datetime.now(UTC)

        db.add(db_obj)
        outbox_id = None
        if lifecycle_event is not None:
            outbox = AccountLifecycleOutbox(
                **lifecycle_event.as_payload() | {"occurred_at": lifecycle_event.occurred_at}
            )
            db.add(outbox)
            await db.flush()
            outbox_id = outbox.id
        await db.commit()
        await db.refresh(db_obj)
        if lifecycle_event is not None:
            from ...user_lifecycle.account_lifecycle_events import queue_account_lifecycle_event

            await queue_account_lifecycle_event(lifecycle_event, outbox_id=outbox_id)
        return db_obj

    async def reactivate(self, db_obj, db: AsyncSession, lifecycle_event: AccountLifecycleEvent | None = None):
        """Sets is_active=True and clears deleted_at. Does NOT touch policy
        assignments: the account gets back exactly what it held before
        deletion, not a silently re-granted or reset set of policies."""
        if not db_obj:
            return None

        db_obj.is_active = True
        db_obj.deleted_at = None

        db.add(db_obj)
        outbox_id = None
        if lifecycle_event is not None:
            outbox = AccountLifecycleOutbox(
                **lifecycle_event.as_payload() | {"occurred_at": lifecycle_event.occurred_at}
            )
            db.add(outbox)
            await db.flush()
            outbox_id = outbox.id
        await db.commit()
        await db.refresh(db_obj)
        if lifecycle_event is not None:
            from ...user_lifecycle.account_lifecycle_events import queue_account_lifecycle_event

            await queue_account_lifecycle_event(lifecycle_event, outbox_id=outbox_id)
        return db_obj

    async def get_deleted_before(self, cutoff: datetime, db: AsyncSession):
        """Every soft-deleted account whose deleted_at is older than
        `cutoff`. Backs the scheduled grace-period purge job
        (procrastinate_tasks/account_purge_tasks.py), which passes
        now - settings.ACCOUNT_PURGE_GRACE_DAYS."""
        result = await db.execute(
            select(self.model).where(self.model.deleted_at.isnot(None), self.model.deleted_at < cutoff)
        )
        return result.scalars().all()

    async def lock_by_id(self, user_id: int, db: AsyncSession):
        """Re-read `user_id` with a row lock (`FOR UPDATE`), or None if it no
        longer exists.

        Exists to close the gap between reading a batch of soft-deleted users
        (get_deleted_before, read once at the start of the nightly purge job)
        and acting on each one later in that same loop: without re-reading
        the row immediately before the irreversible hard delete, a user who
        reactivates in between keeps the stale snapshot the batch read
        started with, and the purge proceeds anyway on data that's no longer
        current. The lock also blocks a concurrent reactivate on the same
        row from landing mid-purge rather than only detecting it after the
        fact. Does not itself require deleted_at to be set: an admin's
        ad-hoc purge of a still-active account is a legitimate, separate
        call shape (see purge_user_account's own deleted_at-regression
        check, which is where that distinction belongs).
        """
        result = await db.execute(select(self.model).where(self.model.id == user_id).with_for_update())
        return result.scalar_one_or_none()
