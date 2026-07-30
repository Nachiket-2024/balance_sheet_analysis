from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from .audit_log_model import AuditLog


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
    async def get_all(db: AsyncSession, limit: int = 100, offset: int = 0) -> list[AuditLog]:
        """Fetch recent entries across all users, newest first."""
        stmt = (
            select(AuditLog)
            .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_for_user(
        user_email: str, db: AsyncSession, limit: int = 100, offset: int = 0
    ) -> list[AuditLog]:
        """Same as get_all, scoped to a single user's events."""
        stmt = (
            select(AuditLog)
            .where(AuditLog.user_email == user_email)
            .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())


audit_log_repository = AuditLogRepository()
