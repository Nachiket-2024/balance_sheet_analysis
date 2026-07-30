from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from ...emails.email_normalization import normalize_email


class UserBaseCRUD:
    """Generic CRUD operations for the users table."""

    def __init__(self, model):
        self.model = model

    async def get_by_id(self, id: int, db: AsyncSession):
        result = await db.execute(select(self.model).where(self.model.id == id))
        return result.scalar_one_or_none()

    async def get_all(self, db: AsyncSession, limit: int = 1000, offset: int = 0):
        # Capped : every other list endpoint in the app (audit log, policy
        # history) bounds its query the same way; this one previously read
        # the whole table unconditionally.
        stmt = select(self.model).order_by(self.model.id).limit(limit).offset(offset)
        result = await db.execute(stmt)
        return result.scalars().all()

    async def create(self, obj_data: dict, db: AsyncSession):
        # Normalized here (rather than trusted from the caller) so every
        # stored row is canonical lowercase regardless of which path created
        # it (signup, OAuth2) : this is the write-side counterpart to
        # UserEmailCRUD.get_by_email's read-side normalization.
        if "email" in obj_data:
            obj_data = {**obj_data, "email": normalize_email(obj_data["email"])}
        obj = self.model(**obj_data)
        db.add(obj)
        await db.commit()
        await db.refresh(obj)
        return obj

    async def update(self, db_obj, update_data: dict, db: AsyncSession):
        if not db_obj:
            return None

        for field, value in update_data.items():
            setattr(db_obj, field, value)

        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def delete(self, db_obj, db: AsyncSession):
        if not db_obj:
            return False

        await db.delete(db_obj)
        await db.commit()
        return True
