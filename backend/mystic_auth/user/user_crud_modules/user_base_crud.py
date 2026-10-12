from datetime import UTC, datetime, timedelta
from typing import Literal

from sqlalchemy import and_, asc, desc, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from ...authorization.models.policy_model import Policy, UserPolicy
from ...authorization.models.user_permission_model import UserPermission
from ...core.search_query import ILIKE_ESCAPE_CHAR, ilike_pattern
from ...emails.email_normalization import normalize_email
from ...user_lifecycle.account_lifecycle_events import AccountLifecycleEvent
from ...user_lifecycle.account_lifecycle_outbox_model import AccountLifecycleOutbox
from ..user_model import UserRole

UserStatus = Literal["active", "inactive", "deleted"]
PermissionSource = Literal["policy", "direct"]

# Relative-bucket presets for the "last login" filter, matching how Okta/
# Auth0/Workspace admin consoles filter this field: quick relative buckets
# first, a custom {from, to} range only when none fit (see
# design/users.html's lastLoginOpts).
LastLoginBucket = Literal["today", "7d", "30d", "90d", "never"]
_LAST_LOGIN_BUCKET_DAYS: dict[str, int] = {"today": 1, "7d": 7, "30d": 30, "90d": 90}

# Allowlisted sort keys, same reasoning as the audit log repositories'
# _SORTABLE_COLUMNS: never let a caller-supplied column name reach the query
# directly. "status" is excluded on purpose: it's a UI-level composite of
# is_active + deleted_at, not one column, so it has no single sensible sort
# order the way the others do.
_SORTABLE_COLUMN_NAMES = {"name", "email", "role", "created_at", "is_verified", "last_login_at"}


class UserBaseCRUD:
    """Generic CRUD operations for the users table."""

    def __init__(self, model):
        self.model = model

    async def get_by_id(self, id: int, db: AsyncSession):
        result = await db.execute(select(self.model).where(self.model.id == id))
        return result.scalar_one_or_none()

    def _search_filter(self, search: str | None):
        # Case-insensitive substring match against name or email. Mirrors
        # UsersPage's old client-side filter, now done server-side since
        # pagination means the frontend no longer has the full list to
        # filter locally.
        if not search:
            return None
        pattern = ilike_pattern(search)
        return or_(
            self.model.name.ilike(pattern, escape=ILIKE_ESCAPE_CHAR),
            self.model.email.ilike(pattern, escape=ILIKE_ESCAPE_CHAR),
        )

    def _status_filter(self, status: UserStatus | None):
        """Status is a UI-level label derived from two real columns, not a
        column of its own: "deleted" is deleted_at IS NOT NULL, "inactive"
        is is_active=False while not deleted, "active" is is_active=True
        while not deleted. Mirrors UsersPage.tsx's badge logic, where
        deleted_at wins over is_active when both would otherwise apply."""
        if status == "deleted":
            return self.model.deleted_at.isnot(None)
        if status == "inactive":
            return (self.model.is_active.is_(False)) & (self.model.deleted_at.is_(None))
        if status == "active":
            return (self.model.is_active.is_(True)) & (self.model.deleted_at.is_(None))
        return None

    def _last_login_filter(
        self, last_login: LastLoginBucket | None, last_login_from: datetime | None, last_login_to: datetime | None
    ):
        if last_login == "never":
            return self.model.last_login_at.is_(None)
        bucket_days = _LAST_LOGIN_BUCKET_DAYS.get(last_login) if last_login else None
        if bucket_days is not None:
            cutoff = datetime.now(UTC) - timedelta(days=bucket_days)
            return self.model.last_login_at.isnot(None) & (self.model.last_login_at >= cutoff)
        # Custom range: either bound alone is enough to filter, same as most
        # date-range pickers (an open-ended "from X" or "up to Y").
        if last_login_from is not None or last_login_to is not None:
            conditions = [self.model.last_login_at.isnot(None)]
            if last_login_from is not None:
                conditions.append(self.model.last_login_at >= last_login_from)
            if last_login_to is not None:
                conditions.append(self.model.last_login_at <= last_login_to)
            return and_(*conditions)
        return None

    def _apply_filters(
        self,
        stmt,
        search: str | None,
        role: UserRole | None,
        is_verified: bool | None,
        status: UserStatus | None,
        policy: str | None = None,
        permission: str | None = None,
        permission_source: PermissionSource | None = None,
        last_login: LastLoginBucket | None = None,
        last_login_from: datetime | None = None,
        last_login_to: datetime | None = None,
    ):
        search_condition = self._search_filter(search)
        if search_condition is not None:
            stmt = stmt.where(search_condition)
        if role is not None:
            stmt = stmt.where(self.model.role == role)
        if is_verified is not None:
            stmt = stmt.where(self.model.is_verified == is_verified)
        status_condition = self._status_filter(status)
        # Verification is an account-state filter in the management UI. When
        # no explicit status is requested, do not let soft-deleted accounts
        # leak into a verified/unverified result; an admin can still combine
        # verification with status="deleted" when intentionally inspecting
        # deactivated accounts.
        if is_verified is not None and status is None:
            status_condition = self._status_filter("active")
        if status_condition is not None:
            stmt = stmt.where(status_condition)
        last_login_condition = self._last_login_filter(last_login, last_login_from, last_login_to)
        if last_login_condition is not None:
            stmt = stmt.where(last_login_condition)
        if policy is not None:
            # A user can hold the matching policy+permission combination via
            # more than one assignment, so the join can multiply rows.
            # distinct() keeps a many-match from showing the same user twice.
            stmt = (
                stmt.join(UserPolicy, UserPolicy.user_id == self.model.id)
                .join(Policy, Policy.id == UserPolicy.policy_id)
                .distinct()
                .where(Policy.name == policy)
            )
            if permission is not None:
                stmt = stmt.where(Policy.actions.contains([permission]))
        elif permission is not None and permission_source == "policy":
            stmt = stmt.where(
                select(UserPolicy.id)
                .join(Policy, Policy.id == UserPolicy.policy_id)
                .where(
                    UserPolicy.user_id == self.model.id,
                    Policy.actions.contains([permission]),
                )
                .exists()
            )
        elif permission is not None and permission_source == "direct":
            stmt = stmt.where(
                select(UserPermission.id)
                .where(
                    and_(
                        UserPermission.user_id == self.model.id,
                        UserPermission.action == permission,
                        UserPermission.is_active.is_(True),
                    )
                )
                .exists()
            )
        elif permission is not None:
            # No policy filter: a user can hold this action via a policy or a
            # direct UserPermission grant (both effective per
            # authorization_service.py), so either must match. Two EXISTS
            # subqueries, not join+distinct, so a user matching several
            # policies/grants still contributes only one row.
            stmt = stmt.where(
                or_(
                    select(UserPolicy.id)
                    .join(Policy, Policy.id == UserPolicy.policy_id)
                    .where(
                        UserPolicy.user_id == self.model.id,
                        Policy.actions.contains([permission]),
                    )
                    .exists(),
                    select(UserPermission.id)
                    .where(
                        and_(
                            UserPermission.user_id == self.model.id,
                            UserPermission.action == permission,
                            UserPermission.is_active.is_(True),
                        )
                    )
                    .exists(),
                )
            )
        return stmt

    def _order_by(self, sort_by: str | None, sort_dir: str):
        column = getattr(self.model, sort_by, None) if sort_by in _SORTABLE_COLUMN_NAMES else None
        if column is None:
            column = self.model.id
        direction = asc if sort_dir == "asc" else desc
        primary = direction(column)
        # Postgres defaults NULLs to sort first on DESC, which would put
        # every never-logged-in user ahead of real, more-recent timestamps
        # on a "most recent login first" sort - the opposite of what an
        # admin sorting this column would expect. Pin last_login_at's NULLs
        # to the bottom regardless of direction; every other sortable column
        # here is NOT NULL, so this never bites them.
        if sort_by == "last_login_at":
            primary = primary.nullslast()
        # id rides along as a secondary key for stable ordering (e.g. many
        # rows sharing the same role), same as the audit log repositories.
        return [primary, direction(self.model.id)]

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
        # Capped, same as every other list endpoint in the app (audit log,
        # policy history); this one previously read the whole table
        # unconditionally.
        stmt = self._apply_filters(
            select(self.model),
            search,
            role,
            is_verified,
            status,
            policy,
            permission,
            permission_source,
            last_login,
            last_login_from,
            last_login_to,
        )
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
        policy: str | None = None,
        permission: str | None = None,
        permission_source: PermissionSource | None = None,
        last_login: LastLoginBucket | None = None,
        last_login_from: datetime | None = None,
        last_login_to: datetime | None = None,
    ) -> int:
        """Total matching rows, ignoring limit/offset. Lets a caller compute
        how many pages exist (see list_all_users' X-Total-Count header).
        Counts distinct ids, not plain rows, since the policy/permission
        filter can join in more than one matching policy row per user (see
        _apply_filters)."""
        stmt = self._apply_filters(
            select(func.count(func.distinct(self.model.id))).select_from(self.model),
            search,
            role,
            is_verified,
            status,
            policy,
            permission,
            permission_source,
            last_login,
            last_login_from,
            last_login_to,
        )
        result = await db.execute(stmt)
        return result.scalar_one()

    async def create(self, obj_data: dict, db: AsyncSession):
        # Normalized here, not trusted from the caller, so every stored row
        # is canonical lowercase regardless of which path created it (signup,
        # OAuth2). Write-side counterpart to UserEmailCRUD.get_by_email's
        # read-side normalization.
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

    async def delete(self, db_obj, db: AsyncSession, lifecycle_event: AccountLifecycleEvent | None = None):
        if not db_obj:
            return False

        outbox_id = None
        if lifecycle_event is not None:
            outbox = AccountLifecycleOutbox(
                **lifecycle_event.as_payload() | {"occurred_at": lifecycle_event.occurred_at}
            )
            db.add(outbox)
            await db.flush()
            outbox_id = outbox.id
        await db.delete(db_obj)
        await db.commit()
        if lifecycle_event is not None:
            from ...user_lifecycle.account_lifecycle_events import queue_account_lifecycle_event

            await queue_account_lifecycle_event(lifecycle_event, outbox_id=outbox_id)
        return True
