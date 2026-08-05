from datetime import UTC, datetime
from typing import cast

from sqlalchemy import func, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from .session_model import UserSession


class SessionRepository:
    """
    Persistence layer for UserSession. Pure CRUD/query concerns only - JWT
    decoding, Redis blocklist calls, and "never let this break the real auth
    flow" try/except live one layer up, in session_service.py.
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
    ) -> UserSession:
        now = datetime.now(UTC)
        session = UserSession(
            user_id=user_id,
            current_jti=jti,
            chain_id=chain_id,
            user_agent=user_agent,
            ip_address=ip_address,
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
        between this table and the real Redis-backed version counters."""
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
        """Ownership-checked: returns None (no-op) if the row doesn't exist,
        belongs to a different user, or is already revoked."""
        session = await SessionRepository.get_by_id(db, session_id)
        if session is None or session.user_id != user_id or session.revoked_at is not None:
            return None

        session.revoked_at = datetime.now(UTC)
        await db.commit()
        await db.refresh(session)
        return session

    @staticmethod
    async def revoke_by_jti(db: AsyncSession, jti: str) -> UserSession | None:
        session = await SessionRepository.get_by_jti(db, jti)
        if session is None or session.revoked_at is not None:
            return None

        session.revoked_at = datetime.now(UTC)
        await db.commit()
        await db.refresh(session)
        return session

    @staticmethod
    async def revoke_by_chain_id(db: AsyncSession, chain_id: str) -> UserSession | None:
        """Used by reuse-detection, where the only identity available is
        the compromised chain_id itself, not a session_id or jti."""
        result = await db.execute(
            select(UserSession).where(UserSession.chain_id == chain_id, UserSession.revoked_at.is_(None))
        )
        session = result.scalar_one_or_none()
        if session is None:
            return None

        session.revoked_at = datetime.now(UTC)
        await db.commit()
        await db.refresh(session)
        return session

    @staticmethod
    async def revoke_all_for_user(db: AsyncSession, user_id: int) -> int:
        stmt = (
            update(UserSession)
            .where(UserSession.user_id == user_id, UserSession.revoked_at.is_(None))
            .values(revoked_at=datetime.now(UTC))
        )
        result = cast(CursorResult, await db.execute(stmt))
        await db.commit()
        return result.rowcount or 0

    @staticmethod
    async def revoke_all_for_user_except_chain(db: AsyncSession, user_id: int, exempt_chain_id: str) -> int:
        """Revoke every active session except the chain that changed password."""
        stmt = (
            update(UserSession)
            .where(
                UserSession.user_id == user_id,
                UserSession.revoked_at.is_(None),
                UserSession.chain_id != exempt_chain_id,
            )
            .values(revoked_at=datetime.now(UTC))
        )
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
