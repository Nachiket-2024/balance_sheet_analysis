from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from .user_crud_modules.user_base_crud import LastLoginBucket, PermissionSource, UserBaseCRUD, UserStatus
from .user_crud_modules.user_email_crud import UserEmailCRUD
from .user_crud_modules.user_lifecycle_crud import UserLifecycleCRUD
from .user_crud_modules.user_role_crud import UserRoleCRUD
from .user_model import User, UserRole


class UserCRUDCollector:
    """Facade over the user CRUD sub-classes (base, email, role, lifecycle),
    forwarding their methods for convenience and IDE discovery."""

    def __init__(self, model):
        self.base = UserBaseCRUD(model)
        self.email = UserEmailCRUD(model)
        self.role = UserRoleCRUD(model)
        self.lifecycle = UserLifecycleCRUD(model)

    async def get_by_id(self, id: int, db: AsyncSession):
        return await self.base.get_by_id(id, db)

    async def get_all(
        self,
        db: AsyncSession,
        limit: int = 1000,
        offset: int = 0,
        search: str | None = None,
        role: UserRole | None = None,
        is_verified: bool | None = None,
        status: UserStatus | None = None,
        sort_by: str | None = None,
        sort_dir: str = "asc",
        policy: str | None = None,
        permission: str | None = None,
        permission_source: PermissionSource | None = None,
        last_login: LastLoginBucket | None = None,
        last_login_from: datetime | None = None,
        last_login_to: datetime | None = None,
    ):
        return await self.base.get_all(
            db,
            limit=limit,
            offset=offset,
            search=search,
            role=role,
            is_verified=is_verified,
            status=status,
            sort_by=sort_by,
            sort_dir=sort_dir,
            policy=policy,
            permission=permission,
            permission_source=permission_source,
            last_login=last_login,
            last_login_from=last_login_from,
            last_login_to=last_login_to,
        )

    async def count(
        self,
        db: AsyncSession,
        search: str | None = None,
        role: UserRole | None = None,
        is_verified: bool | None = None,
        status: UserStatus | None = None,
        policy: str | None = None,
        permission: str | None = None,
        permission_source: PermissionSource | None = None,
        last_login: LastLoginBucket | None = None,
        last_login_from: datetime | None = None,
        last_login_to: datetime | None = None,
    ) -> int:
        return await self.base.count(
            db, search=search, role=role, is_verified=is_verified, status=status, policy=policy, permission=permission,
            permission_source=permission_source,
            last_login=last_login, last_login_from=last_login_from, last_login_to=last_login_to,
        )

    async def create(self, obj_data: dict, db: AsyncSession):
        return await self.base.create(obj_data, db)

    async def update(self, db_obj, update_data: dict, db: AsyncSession):
        return await self.base.update(db_obj, update_data, db)

    async def delete(self, db_obj, db: AsyncSession, lifecycle_event=None):
        return await self.base.delete(db_obj, db, lifecycle_event=lifecycle_event)

    async def get_by_email(self, email: str, db: AsyncSession):
        return await self.email.get_by_email(email, db)

    async def update_by_email(self, email: str, update_data: dict, db: AsyncSession):
        return await self.email.update_by_email(email, update_data, db)

    async def get_by_emails(self, emails: list[str], db: AsyncSession) -> dict[str, User]:
        return await self.email.get_by_emails(emails, db)

    async def update_role(self, db_obj, role: UserRole, db: AsyncSession):
        return await self.role.update_role(db_obj, role, db)

    async def bulk_update_role(self, valid_items: list[tuple[User, UserRole]], db: AsyncSession):
        return await self.role.bulk_update_role(valid_items, db)

    async def soft_delete(self, db_obj, db: AsyncSession, lifecycle_event=None):
        return await self.lifecycle.soft_delete(db_obj, db, lifecycle_event=lifecycle_event)

    async def reactivate(self, db_obj, db: AsyncSession, lifecycle_event=None):
        return await self.lifecycle.reactivate(db_obj, db, lifecycle_event=lifecycle_event)

    async def get_deleted_before(self, cutoff, db: AsyncSession):
        return await self.lifecycle.get_deleted_before(cutoff, db)

    async def lock_by_id(self, user_id: int, db: AsyncSession):
        return await self.lifecycle.lock_by_id(user_id, db)


# Always import this instance (not the class) wherever CRUD operations are needed.
user_crud = UserCRUDCollector(User)

__all__ = [
    "UserBaseCRUD",
    "UserEmailCRUD",
    "UserRoleCRUD",
    "UserLifecycleCRUD",
    "UserCRUDCollector",
    "UserStatus",
    "LastLoginBucket",
    "user_crud",
]
