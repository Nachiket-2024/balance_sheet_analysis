from datetime import datetime
from typing import cast

from sqlalchemy import Select, asc, desc, func, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.sql.elements import OrderByList, UnaryExpression

from ...core.search_query import ILIKE_ESCAPE_CHAR, ilike_pattern
from ..models.authorization_audit_log_model import AuthorizationAuditLog

# user_email here isn't nullable (every row needs an acting user - see
# AuthorizationAuditLog's model comment), unlike security_audit_log's.
# anonymize_for_user below replaces a purged account's real address with
# this fixed sentinel rather than NULL, so the column constraint holds
# while the original identity is no longer recoverable.
ANONYMIZED_USER_EMAIL = "[deleted-account]"

# See backend/mystic_auth/audit_log/audit_log_repository.py's identical constant for why this is
# an allowlist rather than an arbitrary caller-supplied column name.
_SORTABLE_COLUMNS = {
    "created_at": AuthorizationAuditLog.created_at,
    "user_email": AuthorizationAuditLog.user_email,
    "action": AuthorizationAuditLog.action,
    "resource_type": AuthorizationAuditLog.resource_type,
    "allowed": AuthorizationAuditLog.allowed,
}


def _order_by(sort_by: str | None, sort_dir: str) -> list[UnaryExpression | OrderByList]:
    column = _SORTABLE_COLUMNS.get(sort_by or "", AuthorizationAuditLog.created_at)
    direction = asc if sort_dir == "asc" else desc
    return [direction(column), direction(AuthorizationAuditLog.id)]


def _apply_filters(
    stmt: Select,
    search: str | None,
    action: str | None,
    resource_type: str | None,
    allowed: bool | None,
    from_: datetime | None = None,
    to: datetime | None = None,
) -> Select:
    """Shared by get_all/get_for_user and count/count_for_user, so a
    filtered page's total always matches what's actually paged through.
    `search` is a substring match on user_email; the rest are exact
    matches against fixed vocabularies. `from_`/`to` bound created_at,
    both inclusive."""
    if search:
        stmt = stmt.where(AuthorizationAuditLog.user_email.ilike(ilike_pattern(search), escape=ILIKE_ESCAPE_CHAR))
    if action:
        stmt = stmt.where(AuthorizationAuditLog.action == action)
    if resource_type:
        stmt = stmt.where(AuthorizationAuditLog.resource_type == resource_type)
    if allowed is not None:
        stmt = stmt.where(AuthorizationAuditLog.allowed == allowed)
    if from_:
        stmt = stmt.where(AuthorizationAuditLog.created_at >= from_)
    if to:
        stmt = stmt.where(AuthorizationAuditLog.created_at <= to)
    return stmt


class AuthorizationAuditLogRepository:
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
    async def create_entries(entries: list[dict], db: AsyncSession) -> None:
        """
        Same as create_entry, but for many rows in one round trip: used by
        AuthorizationService.authorize_batch, which otherwise issues one
        commit per check (1-50 per request, see
        BatchAuthorizationCheckRequest) purely to persist that check's own
        audit row. Callers here don't need the inserted rows back
        (authorize_batch only needs the decisions, already computed), so
        this skips refresh() too.
        """
        if not entries:
            return
        db.add_all([AuthorizationAuditLog(**data) for data in entries])
        await db.commit()

    @staticmethod
    async def anonymize_for_user(user_email: str, db: AsyncSession) -> int:
        """Strips this account's identity from its own historical PBAC
        decision rows in place. Called once from purge_user_account right
        after the user row itself is hard-deleted (same reasoning as
        AuditLogRepository.anonymize_for_user - see that docstring).

        user_email becomes ANONYMIZED_USER_EMAIL (the column isn't
        nullable). context is cleared entirely: it's the one place this
        table can carry an IP address (see request_context_builder.py), and
        it's an evaluation-time debugging aid with no ongoing use once the
        account is gone. action/resource_type/allowed/candidate_policy_names/
        granting_policy_names/failed_conditions/created_at are left
        untouched - they describe what the policy engine decided, not who
        the acting account was, and keep their aggregate audit value.

        Also called by the scheduled retention job for rows past
        settings.AUDIT_LOG_RETENTION_DAYS regardless of account status.
        Returns the number of rows anonymized (for logging only)."""
        stmt = (
            update(AuthorizationAuditLog)
            .where(AuthorizationAuditLog.user_email == user_email)
            .values(user_email=ANONYMIZED_USER_EMAIL, context=None)
        )
        result = cast(CursorResult, await db.execute(stmt))
        await db.commit()
        return result.rowcount or 0

    @staticmethod
    async def anonymize_older_than(cutoff: datetime, db: AsyncSession) -> int:
        """Retention backstop, mirrors AuditLogRepository.anonymize_older_than.
        Excludes rows already anonymized so re-running this stays a no-op
        for them."""
        stmt = (
            update(AuthorizationAuditLog)
            .where(AuthorizationAuditLog.created_at < cutoff)
            .where(AuthorizationAuditLog.user_email != ANONYMIZED_USER_EMAIL)
            .values(user_email=ANONYMIZED_USER_EMAIL, context=None)
        )
        result = cast(CursorResult, await db.execute(stmt))
        await db.commit()
        return result.rowcount or 0

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
        from_: datetime | None = None,
        to: datetime | None = None,
    ) -> list[AuthorizationAuditLog]:
        """Fetch entries across all users. `search` is a case-insensitive
        substring match on user_email; `action`/`resource_type`/`allowed`
        are exact-match filters. `sort_by`/`sort_dir` default to
        newest-first by created_at, same as before sorting existed."""
        stmt = _apply_filters(select(AuthorizationAuditLog), search, action, resource_type, allowed, from_, to)
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
        from_: datetime | None = None,
        to: datetime | None = None,
    ) -> list[AuthorizationAuditLog]:
        """Same as get_all, scoped to a single user's decisions (no
        `search`: there's nothing left for a user-email search to narrow
        once already scoped to one user)."""
        stmt = select(AuthorizationAuditLog).where(AuthorizationAuditLog.user_email == user_email)
        stmt = _apply_filters(stmt, None, action, resource_type, allowed, from_, to)
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
        from_: datetime | None = None,
        to: datetime | None = None,
    ) -> int:
        """Total matching rows across all users, ignoring limit/offset - lets
        a caller compute how many pages exist (see list_audit_log's
        X-Total-Count header)."""
        stmt = _apply_filters(
            select(func.count()).select_from(AuthorizationAuditLog), search, action, resource_type, allowed, from_, to
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
        from_: datetime | None = None,
        to: datetime | None = None,
    ) -> int:
        stmt = select(func.count()).select_from(AuthorizationAuditLog).where(
            AuthorizationAuditLog.user_email == user_email
        )
        stmt = _apply_filters(stmt, None, action, resource_type, allowed, from_, to)
        result = await db.execute(stmt)
        return result.scalar_one()


authorization_audit_log_repository = AuthorizationAuditLogRepository()
