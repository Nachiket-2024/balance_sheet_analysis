from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from ...user_table.user_model import UserRole


class UserRoleCRUD:
    """Role-specific CRUD operations for the users table."""

    def __init__(self, model):
        self.model = model

    async def get_by_role(self, role: UserRole, db: AsyncSession):
        result = await db.execute(
            select(self.model).where(self.model.role == role)
        )
        return result.scalars().all()

    async def update_role(self, db_obj, role: UserRole, db: AsyncSession):
        if not db_obj:
            return None

        db_obj.role = role

        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj
