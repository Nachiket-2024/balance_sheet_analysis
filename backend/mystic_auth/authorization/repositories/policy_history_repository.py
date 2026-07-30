from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from ..models.policy_history_model import PolicyHistory


class PolicyHistoryRepository:
    """
    Persistence layer for the policy_history table. Entries are written by
    PolicyRepository's create/update/delete (the only places a policy is
    ever mutated) and never updated afterwards, only queried back for
    inspection, comparison, or as the source of a rollback.
    """

    @staticmethod
    def add_entry(data: dict, db: AsyncSession) -> PolicyHistory:
        """
        Stages a new PolicyHistory row via db.add without committing:
        PolicyRepository's create/update/delete call this alongside their
        own policy mutation and commit both together, so a history entry
        can never be recorded without the mutation it describes actually
        having happened (or vice versa).
        """
        entry = PolicyHistory(**data)
        db.add(entry)
        return entry

    @staticmethod
    async def get_for_policy(
        policy_name: str, db: AsyncSession, limit: int = 100, offset: int = 0
    ) -> list[PolicyHistory]:
        stmt = (
            select(PolicyHistory)
            .where(PolicyHistory.policy_name == policy_name)
            .order_by(PolicyHistory.created_at.desc(), PolicyHistory.id.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_by_id(history_id: int, db: AsyncSession) -> PolicyHistory | None:
        result = await db.execute(select(PolicyHistory).where(PolicyHistory.id == history_id))
        return result.scalar_one_or_none()


policy_history_repository = PolicyHistoryRepository()
