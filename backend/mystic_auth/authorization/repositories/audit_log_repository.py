from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from ..models.audit_log_model import AuthorizationAuditLog


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
    async def get_all(db: AsyncSession, limit: int = 100, offset: int = 0) -> list[AuthorizationAuditLog]:
        """Fetch recent entries across all users, newest first."""
        stmt = (
            select(AuthorizationAuditLog)
            .order_by(AuthorizationAuditLog.created_at.desc(), AuthorizationAuditLog.id.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_for_user(
        user_email: str, db: AsyncSession, limit: int = 100, offset: int = 0
    ) -> list[AuthorizationAuditLog]:
        """Same as get_all, scoped to a single user's decisions."""
        stmt = (
            select(AuthorizationAuditLog)
            .where(AuthorizationAuditLog.user_email == user_email)
            .order_by(AuthorizationAuditLog.created_at.desc(), AuthorizationAuditLog.id.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())


audit_log_repository = AuditLogRepository()
