from datetime import UTC, datetime, timedelta

from sqlalchemy import Column, Select, asc, case, desc, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.sql.elements import UnaryExpression

from .audit_log_model import AuditLog

# Duplicated from audit_log_service.py's LOGIN_SUCCESS/LOGIN_FAILURE/
# OAUTH2_LOGIN_SUCCESS constants rather than imported: that module already
# imports this one (via log_security_event -> audit_log_repository), so
# importing back here would be circular. Keep these two lists in sync if
# that event-type vocabulary ever changes.
_LOGIN_EVENT_TYPES = ("login_success", "login_failure", "oauth2_login_success")

# Allowlisted sort keys (frontend column -> real column), never an arbitrary
# caller-supplied column name: letting `sort_by` reach an f-string/getattr
# straight into the query would be a SQL-injection-adjacent footgun, and an
# allowlist is also what keeps "sortable" a deliberate, reviewed set of
# columns rather than every column this model happens to have.
_SORTABLE_COLUMNS: dict[str, Column] = {
    "created_at": AuditLog.created_at,
    "user_email": AuditLog.user_email,
    "event_type": AuditLog.event_type,
    "ip_address": AuditLog.ip_address,
    "success": AuditLog.success,
}


def _order_by(sort_by: str | None, sort_dir: str) -> list[UnaryExpression]:
    """`id` rides along as a secondary key in the same direction as the
    requested column, purely for stable ordering (e.g. many rows sharing the
    same event_type) - not itself a sortable column."""
    column = _SORTABLE_COLUMNS.get(sort_by or "", AuditLog.created_at)
    direction = asc if sort_dir == "asc" else desc
    return [direction(column), direction(AuditLog.id)]


def _apply_filters(
    stmt: Select,
    search: str | None,
    event_type: str | None,
    ip_address: str | None,
    success: bool | None,
) -> Select:
    """Shared by get_all/get_for_user (row fetch) and count/count_for_user
    (X-Total-Count), so a filtered page's total always matches what's
    actually being paged through. `search` (user_email) and `ip_address` are
    substring matches on free-text fields; `event_type`/`success` are exact
    matches against fixed vocabularies (this module's own event_type
    constants, and a bool)."""
    if search:
        stmt = stmt.where(AuditLog.user_email.ilike(f"%{search}%"))
    if event_type == "login":
        # UI-only alias (see frontend securityEventTypes.ts): the filter
        # dropdown offers one "login" option instead of separately listing
        # "login_success" and "login_failure" - that pairing was redundant
        # with the already-present Result filter, which is what actually
        # narrows a login search to one outcome or the other.
        stmt = stmt.where(AuditLog.event_type.in_(("login_success", "login_failure")))
    elif event_type:
        stmt = stmt.where(AuditLog.event_type == event_type)
    if ip_address:
        stmt = stmt.where(AuditLog.ip_address.ilike(f"%{ip_address}%"))
    if success is not None:
        stmt = stmt.where(AuditLog.success == success)
    return stmt


class AuditLogRepository:
    """
    Persistence layer for the security audit log. Append-only: entries are
    created by audit_log_service.log_security_event and never updated; only
    queried back for inspection.
    """

    @staticmethod
    async def create_entry(data: dict, db: AsyncSession) -> AuditLog:
        entry = AuditLog(**data)
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
        event_type: str | None = None,
        ip_address: str | None = None,
        success: bool | None = None,
        sort_by: str | None = None,
        sort_dir: str = "desc",
    ) -> list[AuditLog]:
        """Fetch entries across all users. `search` is a case-insensitive
        substring match on user_email; unattributable rows (user_email is
        NULL, see audit_log_service.py) never match a non-empty search, same
        as they'd never match a literal email typed into a search box.
        `sort_by`/`sort_dir` default to newest-first by created_at, same as
        before sorting existed."""
        stmt = _apply_filters(select(AuditLog), search, event_type, ip_address, success)
        stmt = stmt.order_by(*_order_by(sort_by, sort_dir)).limit(limit).offset(offset)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_for_user(
        user_email: str,
        db: AsyncSession,
        limit: int = 100,
        offset: int = 0,
        event_type: str | None = None,
        ip_address: str | None = None,
        success: bool | None = None,
        sort_by: str | None = None,
        sort_dir: str = "desc",
    ) -> list[AuditLog]:
        """Same as get_all, scoped to a single user's events (no `search`:
        there's nothing left for a user-email search to narrow once already
        scoped to one user)."""
        stmt = select(AuditLog).where(AuditLog.user_email == user_email)
        stmt = _apply_filters(stmt, None, event_type, ip_address, success)
        stmt = stmt.order_by(*_order_by(sort_by, sort_dir)).limit(limit).offset(offset)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def count(
        db: AsyncSession,
        search: str | None = None,
        event_type: str | None = None,
        ip_address: str | None = None,
        success: bool | None = None,
    ) -> int:
        """Total matching rows across all users, ignoring limit/offset - lets
        a caller compute how many pages exist (see list_security_audit_log's
        X-Total-Count header)."""
        stmt = _apply_filters(select(func.count()).select_from(AuditLog), search, event_type, ip_address, success)
        result = await db.execute(stmt)
        return result.scalar_one()

    @staticmethod
    async def count_for_user(
        user_email: str,
        db: AsyncSession,
        event_type: str | None = None,
        ip_address: str | None = None,
        success: bool | None = None,
    ) -> int:
        stmt = select(func.count()).select_from(AuditLog).where(AuditLog.user_email == user_email)
        stmt = _apply_filters(stmt, None, event_type, ip_address, success)
        result = await db.execute(stmt)
        return result.scalar_one()

    @staticmethod
    async def get_login_trend(
        db: AsyncSession, days: int = 14, user_email: str | None = None
    ) -> list[dict]:
        """
        Daily success/failure counts for login-shaped events (password
        login, OAuth2 login) over the last `days` days (today inclusive),
        backing the Audit Log page's login trend chart. Scoped to
        `user_email` when given, otherwise across every user.

        Every day in the range is present in the result even on a day with
        zero matching events, so the chart's x-axis is always continuous
        rather than silently skipping quiet days.
        """
        # Bucketed in UTC explicitly (both the `since` cutoff and the day
        # truncation below), rather than trusting the server process's local
        # timezone or the DB session's timezone setting to agree with it:
        # otherwise events near midnight can land in the wrong day bucket.
        since = datetime.now(UTC).date() - timedelta(days=days - 1)

        day_expr = func.date(func.timezone("UTC", AuditLog.created_at))
        stmt = (
            select(
                day_expr.label("day"),
                func.sum(case((AuditLog.success.is_(True), 1), else_=0)).label("success"),
                func.sum(case((AuditLog.success.is_(False), 1), else_=0)).label("failure"),
            )
            .where(AuditLog.event_type.in_(_LOGIN_EVENT_TYPES))
            .where(day_expr >= since)
        )
        if user_email:
            stmt = stmt.where(AuditLog.user_email == user_email)
        stmt = stmt.group_by(day_expr)

        result = await db.execute(stmt)
        counts_by_day = {row.day.isoformat(): (row.success, row.failure) for row in result}

        return [
            {
                "date": (since + timedelta(days=i)).isoformat(),
                "success": counts_by_day.get((since + timedelta(days=i)).isoformat(), (0, 0))[0],
                "failure": counts_by_day.get((since + timedelta(days=i)).isoformat(), (0, 0))[1],
            }
            for i in range(days)
        ]


audit_log_repository = AuditLogRepository()
