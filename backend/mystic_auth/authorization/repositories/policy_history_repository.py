from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from ..models.policy_history_model import PolicyHistory


class PolicyHistoryRepository:
    """Persistence layer for the policy_history table. Entries are
    written by PolicyRepository's create/update/delete and never updated
    afterwards, only queried for inspection, comparison, or rollback."""

    @staticmethod
    def add_entry(data: dict, db: AsyncSession) -> PolicyHistory:
        """Stages a PolicyHistory row without committing: callers commit
        it together with their own policy mutation, so history can't
        exist without the change it describes (or vice versa)."""
        entry = PolicyHistory(**data)
        db.add(entry)
        return entry

    @staticmethod
    async def get_for_policy(
        policy_name: str, db: AsyncSession, limit: int = 100, offset: int = 0
    ) -> list[PolicyHistory]:
        # Ordered by id, not created_at: created_at is set at transaction
        # start, so under concurrent commits it can be out of commit order.
        # id is assigned at INSERT, so it reflects true commit order.
        stmt = (
            select(PolicyHistory)
            .where(PolicyHistory.policy_name == policy_name)
            .order_by(PolicyHistory.id.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_by_id(history_id: int, db: AsyncSession) -> PolicyHistory | None:
        result = await db.execute(select(PolicyHistory).where(PolicyHistory.id == history_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def count_for_policy(policy_name: str, db: AsyncSession) -> int:
        result = await db.execute(
            select(func.count()).select_from(PolicyHistory).where(PolicyHistory.policy_name == policy_name)
        )
        return int(result.scalar_one())


policy_history_repository = PolicyHistoryRepository()
