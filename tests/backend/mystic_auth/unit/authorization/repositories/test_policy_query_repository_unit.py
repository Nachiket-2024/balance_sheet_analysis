from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql import select

from backend.mystic_auth.authorization.models.policy_model import Policy
from backend.mystic_auth.authorization.repositories.policy_query_repository import (
    PolicyQueryRepository,
    _apply_filters,
)


def _policy() -> Policy:
    now = datetime.now(UTC)
    return Policy(
        id=7,
        name="report_viewer",
        description="Read reports",
        actions=["reports:view"],
        resource_type="reports",
        conditions=None,
        is_active=True,
        created_at=now,
        updated_at=now,
        created_by="system",
    )


@pytest.mark.asyncio
async def test_policy_list_read_schema_includes_aggregate_holder_count():
    db = MagicMock()
    result = MagicMock()
    result.all.return_value = [(_policy(), 4)]
    db.execute = AsyncMock(return_value=result)

    rows = await PolicyQueryRepository.get_all_as_read_schemas(db, limit=25, sort_by="name", sort_dir="asc")

    assert len(rows) == 1
    assert rows[0].name == "report_viewer"
    assert rows[0].holder_count == 4
    db.execute.assert_awaited_once()


def test_destructive_filter_is_explicitly_catalog_scoped():
    statement = _apply_filters(select(Policy), None, None, None, destructive_only=True)
    compiled_statement = statement.compile(dialect=postgresql.dialect())
    compiled = str(compiled_statement)

    assert "user_policies" not in compiled
    assert "policies.actions &&" in compiled
    assert set(compiled_statement.params["actions_1"]) >= {"users:delete_any", "policies:delete"}
