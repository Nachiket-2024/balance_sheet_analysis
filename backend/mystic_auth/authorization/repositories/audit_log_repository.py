from sqlalchemy import Select, asc, desc, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.sql.elements import UnaryExpression

from ..models.audit_log_model import AuthorizationAuditLog

# See audit_log/audit_log_repository.py's identical constant for why this is
# an allowlist rather than an arbitrary caller-supplied column name.
_SORTABLE_COLUMNS = {
    "created_at": AuthorizationAuditLog.created_at,
    "user_email": AuthorizationAuditLog.user_email,
    "action": AuthorizationAuditLog.action,
    "resource_type": AuthorizationAuditLog.resource_type,
    "allowed": AuthorizationAuditLog.allowed,
}


def _order_by(sort_by: str | None, sort_dir: str) -> list[UnaryExpression]:
    column = _SORTABLE_COLUMNS.get(sort_by or "", AuthorizationAuditLog.created_at)
    direction = asc if sort_dir == "asc" else desc
    return [direction(column), direction(AuthorizationAuditLog.id)]


def _apply_filters(
    stmt: Select,
    search: str | None,
    action: str | None,
    resource_type: str | None,
    allowed: bool | None,
) -> Select:
    """Shared by get_all/get_for_user (row fetch) and count/count_for_user
    (X-Total-Count), so a filtered page's total always matches what's
    actually being paged through. `search` is a substring match on
    user_email (a free-text field); `action`/`resource_type`/`allowed` are
    exact matches against fixed, finite vocabularies (Permission's action
    strings, this app's resource types, and a bool), the same distinction
    security_audit_log_repository.py draws for search vs. event_type/success."""
    if search:
        stmt = stmt.where(AuthorizationAuditLog.user_email.ilike(f"%{search}%"))
    if action:
        stmt = stmt.where(AuthorizationAuditLog.action == action)
    if resource_type:
        stmt = stmt.where(AuthorizationAuditLog.resource_type == resource_type)
    if allowed is not None:
        stmt = stmt.where(AuthorizationAuditLog.allowed == allowed)
    return stmt


class AuditLogRepository:
    """
    Persistence layer for the authorization audit log. Append-only:
    entries are created by AuthorizationService.authorize_detailed and
    never updated; only queried back for inspection.
    """

    @staticmethod
    async def create_entry(data: dict, db: AsyncSession) -> AuthorizationAuditLog:
        entry = AuthorizationAuditLog(**data)
        db.add(entry)
        await db.commit()
        await db.refresh(entry)
        return entry

    @staticmethod
    async def get_all(
        db: AsyncSession,
        limit: int = 100,
        offset: int = 0,
        search: str | None = None,
        action: str | None = None,
        resource_type: str | None = None,
        allowed: bool | None = None,
        sort_by: str | None = None,
        sort_dir: str = "desc",
    ) -> list[AuthorizationAuditLog]:
        """Fetch entries across all users. `search` is a case-insensitive
        substring match on user_email; `action`/`resource_type`/`allowed`
        are exact-match filters. `sort_by`/`sort_dir` default to
        newest-first by created_at, same as before sorting existed."""
        stmt = _apply_filters(select(AuthorizationAuditLog), search, action, resource_type, allowed)
        stmt = stmt.order_by(*_order_by(sort_by, sort_dir)).limit(limit).offset(offset)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_for_user(
        user_email: str,
        db: AsyncSession,
        limit: int = 100,
        offset: int = 0,
        action: str | None = None,
        resource_type: str | None = None,
        allowed: bool | None = None,
        sort_by: str | None = None,
        sort_dir: str = "desc",
    ) -> list[AuthorizationAuditLog]:
        """Same as get_all, scoped to a single user's decisions (no
        `search`: there's nothing left for a user-email search to narrow
        once already scoped to one user)."""
        stmt = select(AuthorizationAuditLog).where(AuthorizationAuditLog.user_email == user_email)
        stmt = _apply_filters(stmt, None, action, resource_type, allowed)
        stmt = stmt.order_by(*_order_by(sort_by, sort_dir)).limit(limit).offset(offset)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def count(
        db: AsyncSession,
        search: str | None = None,
        action: str | None = None,
        resource_type: str | None = None,
        allowed: bool | None = None,
    ) -> int:
        """Total matching rows across all users, ignoring limit/offset - lets
        a caller compute how many pages exist (see list_audit_log's
        X-Total-Count header)."""
        stmt = _apply_filters(
            select(func.count()).select_from(AuthorizationAuditLog), search, action, resource_type, allowed
        )
        result = await db.execute(stmt)
        return result.scalar_one()

    @staticmethod
    async def count_for_user(
        user_email: str,
        db: AsyncSession,
        action: str | None = None,
        resource_type: str | None = None,
        allowed: bool | None = None,
    ) -> int:
        stmt = select(func.count()).select_from(AuthorizationAuditLog).where(
            AuthorizationAuditLog.user_email == user_email
        )
        stmt = _apply_filters(stmt, None, action, resource_type, allowed)
        result = await db.execute(stmt)
        return result.scalar_one()


audit_log_repository = AuditLogRepository()
