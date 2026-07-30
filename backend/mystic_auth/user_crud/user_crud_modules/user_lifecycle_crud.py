from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession


class UserLifecycleCRUD:
    """
    Account-lifecycle-specific CRUD operations for the users table.

    Deliberately separate from UserBaseCRUD.update: both operations touch
    exactly two columns (is_active, deleted_at) with app-computed values, not
    caller-supplied ones, so they don't belong behind the generic "update with
    an arbitrary dict" entry point the way a profile edit does : that dict
    would let a caller set deleted_at to anything.
    """

    def __init__(self, model):
        self.model = model

    async def soft_delete(self, db_obj, db: AsyncSession):
        """Sets is_active=False (the flag login_service.py, oauth2_service.py,
        and current_user_handler.py already gate on) and deleted_at=now."""
        if not db_obj:
            return None

        db_obj.is_active = False
        db_obj.deleted_at = datetime.now(UTC)

        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def reactivate(self, db_obj, db: AsyncSession):
        """Sets is_active=True and clears deleted_at. Deliberately does NOT
        touch policy assignments : whatever the account held before deletion
        is what it holds again, restored exactly as an admin left it, not
        silently re-granted or reset."""
        if not db_obj:
            return None

        db_obj.is_active = True
        db_obj.deleted_at = None

        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj
