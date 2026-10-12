from sqlalchemy.ext.asyncio import AsyncSession

from ...authorization.schemas.bulk_schema import BulkItemResult
from ..user_model import User, UserRole


class UserRoleCRUD:
    """Role-specific CRUD operations for the users table."""

    def __init__(self, model):
        self.model = model

    async def update_role(self, db_obj, role: UserRole, db: AsyncSession):
        if not db_obj:
            return None

        db_obj.role = role

        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def bulk_update_role(
        self, valid_items: list[tuple[User, UserRole]], db: AsyncSession
    ) -> list[BulkItemResult]:
        """
        `valid_items` is every (User, UserRole) pair that already passed
        resolution and the same per-item safeguards update_user_role
        (user_management_update_routes.py) enforces, e.g. system-role
        targets blocked, users:assign_system_role required to assign
        `system`. Stages every write and commits once for the whole batch;
        see bulk_schema.py's best-effort-except-commit-failure contract,
        mirrored below.
        """
        if not valid_items:
            return []

        results: list[BulkItemResult] = []
        for user, role in valid_items:
            user.role = role
            db.add(user)
            results.append(BulkItemResult(user_email=user.email, identifier=role.value, status="success"))

        try:
            await db.commit()
        except Exception:
            await db.rollback()
            return [
                BulkItemResult(user_email=r.user_email, identifier=r.identifier, status="error", error="commit_failed")
                for r in results
            ]

        return results
