from datetime import UTC, datetime, timedelta
from typing import cast

from sqlalchemy import Select, asc, case, desc, func, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.sql.elements import ColumnElement, OrderByList, UnaryExpression

from ..core.search_query import ILIKE_ESCAPE_CHAR, ilike_pattern
from .audit_log_model import AuditLog

# Duplicated (not imported) from audit_log_service.py's LOGIN_SUCCESS/
# LOGIN_FAILURE/OAUTH2_LOGIN_SUCCESS constants: that module already imports
# this one via log_security_event, so importing back would be circular. Keep
# the two lists in sync if the event-type vocabulary changes.
_LOGIN_EVENT_TYPES = ("login_success", "login_failure", "oauth2_login_success")

# UI-only alias (see UserAccessDialog's Details tab "Recent access changes"):
# every event type that represents an admin changing what a user is allowed
# to do, as opposed to that user's own auth activity (login, password reset,
# etc). Duplicated (not imported) from audit_log_service.py's own constants
# for the same reason _LOGIN_EVENT_TYPES is: that module already imports this
# one via log_security_event, so importing back would be circular.
_ACCESS_CHANGE_EVENT_TYPES = (
    "policy_assigned",
    "policy_revoked",
    "policy_action_revoked",
    "permission_granted",
    "permission_revoked",
    "user_role_changed",
)

# Allowlisted sort keys (frontend column -> real column). Never let a
# caller-supplied column name reach the query directly.
_SORTABLE_COLUMNS: dict[str, ColumnElement] = {
    "created_at": AuditLog.created_at,
    "user_email": AuditLog.user_email,
    "event_type": AuditLog.event_type,
    "ip_address": AuditLog.ip_address,
    "success": AuditLog.success,
}


def _order_by(sort_by: str | None, sort_dir: str) -> list[UnaryExpression | OrderByList]:
    """`id` rides along as a secondary key for stable ordering (e.g. many
    rows sharing the same event_type). Not itself a sortable column."""
    column = _SORTABLE_COLUMNS.get(sort_by or "") or AuditLog.created_at
    direction = asc if sort_dir == "asc" else desc
    return [direction(column), direction(AuditLog.id)]


def _apply_filters(
    stmt: Select,
    search: str | None,
    event_type: str | None,
    ip_address: str | None,
    success: bool | None,
    from_: datetime | None = None,
    to: datetime | None = None,
) -> Select:
    """Shared by get_all/get_for_user (row fetch) and count/count_for_user
    (X-Total-Count) so a filtered page's total always matches what's
    actually being paged through. `search`/`ip_address` are substring
    matches; `event_type`/`success` are exact matches. `from_`/`to` bound
    created_at, both inclusive."""
    if search:
        stmt = stmt.where(AuditLog.user_email.ilike(ilike_pattern(search), escape=ILIKE_ESCAPE_CHAR))
    if event_type == "login":
        # UI-only alias (see frontend securityEventTypes.ts): the filter
        # dropdown offers one "login" option instead of listing
        # login_success/login_failure separately. The Result filter already
        # covers narrowing to one outcome or the other.
        stmt = stmt.where(AuditLog.event_type.in_(("login_success", "login_failure")))
    elif event_type == "access_change":
        stmt = stmt.where(AuditLog.event_type.in_(_ACCESS_CHANGE_EVENT_TYPES))
    elif event_type:
        stmt = stmt.where(AuditLog.event_type == event_type)
    if ip_address:
        stmt = stmt.where(AuditLog.ip_address.ilike(ilike_pattern(ip_address), escape=ILIKE_ESCAPE_CHAR))
    if success is not None:
        stmt = stmt.where(AuditLog.success == success)
    if from_:
        stmt = stmt.where(cast(ColumnElement[bool], AuditLog.created_at >= from_))
    if to:
        stmt = stmt.where(cast(ColumnElement[bool], AuditLog.created_at <= to))
    return stmt


class AuditLogRepository:
    """
    Persistence layer for the security audit log. Append-only: entries are
    created by audit_log_service.log_security_event and never updated, only
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
        from_: datetime | None = None,
        to: datetime | None = None,
    ) -> list[AuditLog]:
        """Fetch entries across all users. `search` is a case-insensitive
        substring match on user_email; rows with no user_email (see
        audit_log_service.py) never match a non-empty search. Defaults to
        newest-first by created_at."""
        stmt = _apply_filters(select(AuditLog), search, event_type, ip_address, success, from_, to)
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
        from_: datetime | None = None,
        to: datetime | None = None,
    ) -> list[AuditLog]:
        """Same as get_all, scoped to a single user's events. No `search`
        parameter: once scoped to one user, there's nothing left for a
        user-email search to narrow."""
        stmt = select(AuditLog).where(AuditLog.user_email == user_email)
        stmt = _apply_filters(stmt, None, event_type, ip_address, success, from_, to)
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
        from_: datetime | None = None,
        to: datetime | None = None,
    ) -> int:
        """Total matching rows across all users, ignoring limit/offset. Lets
        a caller compute how many pages exist (see list_security_audit_log's
        X-Total-Count header)."""
        stmt = _apply_filters(
            select(func.count()).select_from(AuditLog), search, event_type, ip_address, success, from_, to
        )
        result = await db.execute(stmt)
        return result.scalar_one()

    @staticmethod
    async def count_for_user(
        user_email: str,
        db: AsyncSession,
        event_type: str | None = None,
        ip_address: str | None = None,
        success: bool | None = None,
        from_: datetime | None = None,
        to: datetime | None = None,
    ) -> int:
        stmt = select(func.count()).select_from(AuditLog).where(AuditLog.user_email == user_email)
        stmt = _apply_filters(stmt, None, event_type, ip_address, success, from_, to)
        result = await db.execute(stmt)
        return result.scalar_one()

    @staticmethod
    async def anonymize_for_user(user_email: str, db: AsyncSession) -> int:
        """Strips this account's PII (email, IP, user-agent) from its own
        historical rows in place. Called once from purge_user_account right
        after the user row itself is hard-deleted, so "deleted" actually
        means the account's identity stops being readable here too, not
        just that the `users` row is gone while every login/logout/
        password-reset event it ever made keeps a plaintext email and IP
        forever (see docs/mystic_auth/concerns - this closes that gap).

        Keeps event_type/success/created_at/metadata/request_id: those
        carry no PII and still have aggregate security value (login trend
        charts, event counts) even with no account left to tie them to.
        user_email -> NULL reuses the same state already used for events
        with no resolvable account (e.g. a failed login against an
        unregistered email) - a purged account's history becomes
        indistinguishable from one of those going forward, which is the
        intent.

        Also called by the scheduled retention job (audit_log_tasks.py) for
        rows past settings.AUDIT_LOG_RETENTION_DAYS regardless of whether
        the account was ever deleted, so this table doesn't accumulate PII
        forever even for accounts that are never purged.

        Returns the number of rows anonymized (for logging only)."""
        stmt = (
            update(AuditLog)
            .where(AuditLog.user_email == user_email)
            .values(user_email=None, ip_address=None, user_agent=None)
        )
        result = cast(CursorResult, await db.execute(stmt))
        await db.commit()
        return result.rowcount or 0

    @staticmethod
    async def anonymize_older_than(cutoff: datetime, db: AsyncSession) -> int:
        """Retention backstop: strips PII from every row older than
        `cutoff`, independent of account status. Only touches rows that
        still have a user_email set, so re-running this doesn't keep
        re-"anonymizing" already-null rows forever."""
        stmt = (
            update(AuditLog)
            .where(cast(ColumnElement[bool], AuditLog.created_at < cutoff))
            .where(AuditLog.user_email.is_not(None))
            .values(user_email=None, ip_address=None, user_agent=None)
        )
        result = cast(CursorResult, await db.execute(stmt))
        await db.commit()
        return result.rowcount or 0

    @staticmethod
    async def get_login_trend(
        db: AsyncSession,
        days: int = 14,
        user_email: str | None = None,
        search: str | None = None,
        from_: datetime | None = None,
        to: datetime | None = None,
    ) -> list[dict]:
        """
        Daily success/failure counts for login-shaped events (password
        login, OAuth2 login) over an exact inclusive time range when
        `from_`/`to` are supplied, or over the last `days` days otherwise.
        Scoped to `user_email` when given, otherwise across every user.

        Every day in the range appears in the result even with zero matching
        events, so the chart's x-axis stays continuous instead of skipping
        quiet days.
        """
        # Bucketed in UTC explicitly, both the cutoff and the day truncation
        # below, so events near midnight always land in the right day
        # regardless of server or DB session timezone.
        if from_ is not None:
            since = from_.astimezone(UTC).date()
            until = (to or from_).astimezone(UTC).date()
        else:
            since = datetime.now(UTC).date() - timedelta(days=days - 1)
            until = datetime.now(UTC).date()
        if until < since:
            return []
        range_days = (until - since).days + 1

        day_expr = func.date(func.timezone("UTC", AuditLog.created_at))
        stmt = (
            select(
                day_expr.label("day"),
                func.sum(case((AuditLog.success.is_(True), 1), else_=0)).label("success"),
                func.sum(case((AuditLog.success.is_(False), 1), else_=0)).label("failure"),
            )
            .where(AuditLog.event_type.in_(_LOGIN_EVENT_TYPES))
            .where(day_expr >= since)
            .where(day_expr <= until)
        )
        if from_:
            stmt = stmt.where(AuditLog.created_at >= from_)
        if to:
            stmt = stmt.where(AuditLog.created_at <= to)
        if user_email:
            stmt = stmt.where(AuditLog.user_email == user_email)
        if search:
            stmt = stmt.where(AuditLog.user_email.ilike(ilike_pattern(search), escape=ILIKE_ESCAPE_CHAR))
        stmt = stmt.group_by(day_expr)

        result = await db.execute(stmt)
        counts_by_day = {row.day.isoformat(): (row.success, row.failure) for row in result}

        return [
            {
                "date": (since + timedelta(days=i)).isoformat(),
                "success": counts_by_day.get((since + timedelta(days=i)).isoformat(), (0, 0))[0],
                "failure": counts_by_day.get((since + timedelta(days=i)).isoformat(), (0, 0))[1],
            }
            for i in range(range_days)
        ]


audit_log_repository = AuditLogRepository()
