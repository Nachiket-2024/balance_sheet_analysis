from sqlalchemy.ext.asyncio import AsyncSession

from ..user_table.user_model import User, UserRole
from .user_crud_modules.user_base_crud import UserBaseCRUD
from .user_crud_modules.user_email_crud import UserEmailCRUD
from .user_crud_modules.user_lifecycle_crud import UserLifecycleCRUD
from .user_crud_modules.user_role_crud import UserRoleCRUD


class UserCRUDCollector:
    """
    Facade over the user CRUD sub-classes (base, email, role, lifecycle),
    forwarding their methods for convenience and IDE discovery.
    """

    def __init__(self, model):
        self.base = UserBaseCRUD(model)
        self.email = UserEmailCRUD(model)
        self.role = UserRoleCRUD(model)
        self.lifecycle = UserLifecycleCRUD(model)

    async def get_by_id(self, id: int, db: AsyncSession):
        return await self.base.get_by_id(id, db)

    async def get_all(self, db: AsyncSession, limit: int = 1000, offset: int = 0):
        return await self.base.get_all(db, limit=limit, offset=offset)

    async def create(self, obj_data: dict, db: AsyncSession):
        return await self.base.create(obj_data, db)

    async def update(self, db_obj, update_data: dict, db: AsyncSession):
        return await self.base.update(db_obj, update_data, db)

    async def delete(self, db_obj, db: AsyncSession):
        return await self.base.delete(db_obj, db)

    async def get_by_email(self, email: str, db: AsyncSession):
        return await self.email.get_by_email(email, db)

    async def update_by_email(self, email: str, update_data: dict, db: AsyncSession):
        return await self.email.update_by_email(email, update_data, db)

    async def get_by_role(self, role: UserRole, db: AsyncSession):
        return await self.role.get_by_role(role, db)

    async def update_role(self, db_obj, role: UserRole, db: AsyncSession):
        return await self.role.update_role(db_obj, role, db)

    async def soft_delete(self, db_obj, db: AsyncSession):
        return await self.lifecycle.soft_delete(db_obj, db)

    async def reactivate(self, db_obj, db: AsyncSession):
        return await self.lifecycle.reactivate(db_obj, db)


# Always import this instance (not the class) wherever CRUD operations are needed.
user_crud = UserCRUDCollector(User)

__all__ = [
    "UserBaseCRUD",
    "UserEmailCRUD",
    "UserRoleCRUD",
    "UserLifecycleCRUD",
    "UserCRUDCollector",
    "user_crud",
]
