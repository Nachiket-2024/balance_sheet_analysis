from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .llm_config import LLM_DAILY_CHAR_BUDGET
from .llm_model import LLMUsage


async def daily_usage_chars(user_email: str, db: AsyncSession) -> int:
    since = datetime.now(UTC) - timedelta(days=1)
    result = await db.execute(select(func.coalesce(func.sum(LLMUsage.input_chars + LLMUsage.output_chars), 0)).where(LLMUsage.user_email == user_email, LLMUsage.created_at >= since))
    return int(result.scalar_one())


def has_budget(used_chars: int, question: str, context: str) -> bool:
    return used_chars + len(question) + len(context) <= LLM_DAILY_CHAR_BUDGET
