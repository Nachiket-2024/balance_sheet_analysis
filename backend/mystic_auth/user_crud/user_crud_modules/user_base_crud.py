from typing import Literal

from sqlalchemy import asc, desc, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from ...emails.email_normalization import normalize_email
from ...user_table.user_model import UserRole

UserStatus = Literal["active", "inactive", "deleted"]

# Allowlisted sort keys, same rationale as the two audit log repositories'
# identical _SORTABLE_COLUMNS: never let a caller-supplied column name reach
# the query directly. "status" is deliberately excluded: it's a UI-level
# composite of is_active + deleted_at, not one column, so there's no single
# sensible sort order for it the way there is for the others.
_SORTABLE_COLUMN_NAMES = {"name", "email", "role", "created_at", "is_verified"}


class UserBaseCRUD:
    """Generic CRUD operations for the users table."""

    def __init__(self, model):
        self.model = model

    async def get_by_id(self, id: int, db: AsyncSession):
        result = await db.execute(select(self.model).where(self.model.id == id))
        return result.scalar_one_or_none()

    def _search_filter(self, search: str | None):
        # Case-insensitive substring match against name or email, mirroring
        # UsersPage's old client-side filter now that pagination means the
        # frontend can no longer just filter an already-fully-loaded list.
        if not search:
            return None
        pattern = f"%{search}%"
        return or_(self.model.name.ilike(pattern), self.model.email.ilike(pattern))

    def _status_filter(self, status: UserStatus | None):
        """Status is a UI-level label derived from two real columns, not a
        column of its own: "deleted" is deleted_at IS NOT NULL; "inactive"
        is is_active=False while NOT deleted; "active" is is_active=True
        while NOT deleted (mirrors UsersPage.tsx's own badge logic:
        deleted_at wins over is_active when both would otherwise apply)."""
        if status == "deleted":
            return self.model.deleted_at.isnot(None)
        if status == "inactive":
            return (self.model.is_active.is_(False)) & (self.model.deleted_at.is_(None))
        if status == "active":
            return (self.model.is_active.is_(True)) & (self.model.deleted_at.is_(None))
        return None

    def _apply_filters(
        self,
        stmt,
        search: str | None,
        role: UserRole | None,
        is_verified: bool | None,
        status: UserStatus | None,
    ):
        search_condition = self._search_filter(search)
        if search_condition is not None:
            stmt = stmt.where(search_condition)
        if role is not None:
            stmt = stmt.where(self.model.role == role)
        if is_verified is not None:
            stmt = stmt.where(self.model.is_verified == is_verified)
        status_condition = self._status_filter(status)
        if status_condition is not None:
            stmt = stmt.where(status_condition)
        return stmt

    def _order_by(self, sort_by: str | None, sort_dir: str):
        column = getattr(self.model, sort_by, None) if sort_by in _SORTABLE_COLUMN_NAMES else None
        if column is None:
            column = self.model.id
        direction = asc if sort_dir == "asc" else desc
        # id as a secondary key for stable ordering (e.g. many rows sharing
        # the same role), same reasoning as the audit log repositories.
        return [direction(column), direction(self.model.id)]

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
    ):
        # Capped : every other list endpoint in the app (audit log, policy
        # history) bounds its query the same way; this one previously read
        # the whole table unconditionally.
        stmt = self._apply_filters(select(self.model), search, role, is_verified, status)
        stmt = stmt.order_by(*self._order_by(sort_by, sort_dir)).limit(limit).offset(offset)
        result = await db.execute(stmt)
        return result.scalars().all()

    async def count(
        self,
        db: AsyncSession,
        search: str | None = None,
        role: UserRole | None = None,
        is_verified: bool | None = None,
        status: UserStatus | None = None,
    ) -> int:
        """Total matching rows, ignoring limit/offset - lets a caller compute
        how many pages exist (see list_all_users' X-Total-Count header)."""
        stmt = self._apply_filters(
            select(func.count()).select_from(self.model), search, role, is_verified, status
        )
        result = await db.execute(stmt)
        return result.scalar_one()

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
