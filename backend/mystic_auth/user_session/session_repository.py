from copy import copy
from datetime import UTC, datetime
from typing import cast

from sqlalchemy import delete, func
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from .session_model import UserSession


class SessionRepository:
    """
    Persistence layer for UserSession. Pure CRUD/query concerns only - JWT
    decoding, token-version and replay-registry calls, and "never let this break the real auth
    flow" try/except live one layer up, in session_service.py.

    Every "revoke" here deletes the row instead of setting revoked_at:
    session_model.py's own docstring establishes Postgres token-version counters
    (not this table) as the source of truth for actual token validity, this
    table being only "a best-effort mirror for display". Nothing else in the
    app (audit_log included) reads a revoked or expired row afterward, so
    keeping it around had no product benefit and only grew the table
    forever. Sessions that lapse via expires_at without ever being
    explicitly revoked aren't caught here (there's no revoke call to hook
    into) - see delete_expired_unrevoked and procrastinate_tasks/
    session_cleanup_tasks.py's periodic sweep for those.
    """

    @staticmethod
    async def create(
        db: AsyncSession,
        user_id: int,
        jti: str,
        chain_id: str,
        expires_at: datetime,
        user_agent: str | None,
        ip_address: str | None,
        city: str | None = None,
        country: str | None = None,
    ) -> UserSession:
        now = datetime.now(UTC)
        session = UserSession(
            user_id=user_id,
            current_jti=jti,
            chain_id=chain_id,
            user_agent=user_agent,
            ip_address=ip_address,
            city=city,
            country=country,
            last_used_at=now,
            expires_at=expires_at,
        )
        db.add(session)
        await db.commit()
        await db.refresh(session)
        return session

    @staticmethod
    async def get_by_jti(db: AsyncSession, jti: str) -> UserSession | None:
        result = await db.execute(select(UserSession).where(UserSession.current_jti == jti))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_id(db: AsyncSession, session_id: int) -> UserSession | None:
        return await db.get(UserSession, session_id)

    @staticmethod
    async def rotate(db: AsyncSession, old_jti: str, new_jti: str, new_expires_at: datetime) -> UserSession | None:
        """Moves an existing row from its old (now-rotated-away) jti to the
        new one minted alongside it, bumping last_used_at. chain_id is
        untouched (it never changes across a rotation). Returns None (a
        no-op, never raises) if no row matched the old jti - covers
        sessions minted before this feature shipped, or any other drift
        between this table and the real Postgres-backed version counters."""
        session = await SessionRepository.get_by_jti(db, old_jti)
        if session is None:
            return None

        session.current_jti = new_jti
        session.expires_at = new_expires_at
        session.last_used_at = datetime.now(UTC)
        await db.commit()
        await db.refresh(session)
        return session

    @staticmethod
    async def list_active_for_user(db: AsyncSession, user_id: int) -> list[UserSession]:
        now = datetime.now(UTC)
        stmt = (
            select(UserSession)
            .where(
                UserSession.user_id == user_id,
                UserSession.revoked_at.is_(None),
                UserSession.expires_at > now,
            )
            .order_by(UserSession.last_used_at.desc())
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def count_active_for_user(db: AsyncSession, user_id: int) -> int:
        """Same filter as list_active_for_user, but a COUNT instead of
        fetching full rows - used for the dashboard's "Active sessions"
        stat, which needs only the number."""
        now = datetime.now(UTC)
        stmt = select(func.count()).select_from(UserSession).where(
            UserSession.user_id == user_id,
            UserSession.revoked_at.is_(None),
            UserSession.expires_at > now,
        )
        result = await db.execute(stmt)
        return result.scalar_one()

    @staticmethod
    async def revoke_by_id(db: AsyncSession, session_id: int, user_id: int) -> UserSession | None:
        """Ownership-checked: returns None (no-op) if the row doesn't exist
        or belongs to a different user. Deletes the row rather than marking
        it revoked - see the class docstring. The returned object is a
        detached snapshot (copy.copy, not tracked by db) taken just before
        the delete: safe for an identity/truthiness check, but don't expect
        it to reflect anything written after this call.

        Deletes by primary key via a Core `delete()` statement, not
        `db.delete(session)`: the ORM form expects to affect exactly one row
        and logs a SAWarning whenever it affects zero, which is exactly what
        happens under a legitimate race (two requests revoking the same
        session at once - see test_manage_sessions_concurrency_integration.py).
        A concurrent delete having already won is still success here, same
        idempotent "this session is gone" outcome that test asserts, just
        without the ORM's own row-count assumption complaining about it."""
        session = await SessionRepository.get_by_id(db, session_id)
        if session is None or session.user_id != user_id:
            return None

        snapshot = copy(session)
        await db.execute(delete(UserSession).where(UserSession.id == session.id))
        await db.commit()
        return snapshot

    @staticmethod
    async def revoke_by_jti(db: AsyncSession, jti: str) -> UserSession | None:
        """Deletes the row rather than marking it revoked - see the class
        docstring. Returned object is a detached pre-delete snapshot, same
        as revoke_by_id, and deletes by primary key for the same
        no-SAWarning-under-a-race reason documented there."""
        session = await SessionRepository.get_by_jti(db, jti)
        if session is None:
            return None

        snapshot = copy(session)
        await db.execute(delete(UserSession).where(UserSession.id == session.id))
        await db.commit()
        return snapshot

    @staticmethod
    async def revoke_by_chain_id(db: AsyncSession, chain_id: str) -> UserSession | None:
        """Used by reuse-detection, where the only identity available is
        the compromised chain_id itself, not a session_id or jti. Deletes
        the row rather than marking it revoked - see the class docstring.
        Deletes by primary key for the same no-SAWarning-under-a-race reason
        documented on revoke_by_id."""
        result = await db.execute(select(UserSession).where(UserSession.chain_id == chain_id))
        session = result.scalar_one_or_none()
        if session is None:
            return None

        snapshot = copy(session)
        await db.execute(delete(UserSession).where(UserSession.id == session.id))
        await db.commit()
        return snapshot

    @staticmethod
    async def revoke_all_for_user(db: AsyncSession, user_id: int) -> int:
        """Deletes every row for the user rather than marking them revoked -
        see the class docstring."""
        stmt = delete(UserSession).where(UserSession.user_id == user_id)
        result = cast(CursorResult, await db.execute(stmt))
        await db.commit()
        return result.rowcount or 0

    @staticmethod
    async def revoke_all_for_user_except_chain(db: AsyncSession, user_id: int, exempt_chain_id: str) -> int:
        """Deletes every row for the user except the chain that changed
        password, rather than marking them revoked - see the class
        docstring."""
        stmt = delete(UserSession).where(
            UserSession.user_id == user_id,
            UserSession.chain_id != exempt_chain_id,
        )
        result = cast(CursorResult, await db.execute(stmt))
        await db.commit()
        return result.rowcount or 0

    @staticmethod
    async def delete_expired_unrevoked(db: AsyncSession, before: datetime) -> int:
        """Sweeps rows that lapsed via expires_at without ever going through
        an explicit revoke call above (those already delete immediately, so
        there's nothing revoked left for this to find - the filter here is
        expires_at alone). `before` is the caller's cutoff (now() minus
        settings.SESSION_ROW_RETENTION_HOURS), not computed here, so
        procrastinate_tasks/session_cleanup_tasks.py and its tests can pin
        an exact instant instead of racing the real clock."""
        stmt = delete(UserSession).where(UserSession.expires_at < before)
        result = cast(CursorResult, await db.execute(stmt))
        await db.commit()
        return result.rowcount or 0

    @staticmethod
    async def rotate_by_chain_id(db: AsyncSession, chain_id: str, new_jti: str, new_expires_at: datetime) -> UserSession | None:
        """Update a session after its exempted chain receives fresh tokens."""
        result = await db.execute(
            select(UserSession).where(UserSession.chain_id == chain_id, UserSession.revoked_at.is_(None))
        )
        session = result.scalar_one_or_none()
        if session is None:
            return None

        session.current_jti = new_jti
        session.expires_at = new_expires_at
        session.last_used_at = datetime.now(UTC)
        await db.commit()
        await db.refresh(session)
        return session


session_repository = SessionRepository()
