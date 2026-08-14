# current_user_handler.py's GET /auth/me response also surfaces `created_at`
# (for the dashboard's "Member since" stat) and `active_sessions` (for its
# "active sessions" stat), the latter sourced from the best-effort Postgres
# mirror (session_service.count_active_sessions), not Redis - real token
# validity is governed by version counters now, which have no "list every
# live session" operation of their own. Only computed when the caller
# explicitly asks for it (include_active_sessions=True, what GET /auth/me
# passes) - every other route sharing this handler via the auth dependency
# never reads this field, so it skips the query entirely by default.
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from backend.mystic_auth.auth.current_user.current_user_handler import (
    current_user_handler,
)
from backend.mystic_auth.user_table.user_model import UserRole

MODULE = "backend.mystic_auth.auth.current_user.current_user_handler"


class _FakeUser:
    def __init__(self, created_at=None):
        self.name = "Test User"
        self.email = "user@example.com"
        self.role = UserRole.user
        self.is_active = True
        self.hashed_password = "hash"
        self.created_at = created_at or datetime(2026, 1, 1, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _mock_authenticated_user_dependencies(mocker):
    mocker.patch(
        f"{MODULE}.jwt_service.verify_token",
        new_callable=AsyncMock,
        return_value={"email": "user@example.com", "role": "user"},
    )
    mocker.patch(f"{MODULE}.user_crud.get_by_email", return_value=_FakeUser())
    mocker.patch(
        f"{MODULE}.policy_repository.get_active_policies_for_user",
        new_callable=AsyncMock,
        return_value=[],
    )


@pytest.mark.asyncio
async def test_created_at_is_returned_as_an_iso_string(mocker):
    mocker.patch(f"{MODULE}.session_service.count_active_sessions", new_callable=AsyncMock, return_value=0)

    result = await current_user_handler.get_current_user("some-token", db=None)

    assert result["created_at"] == datetime(2026, 1, 1, tzinfo=UTC).isoformat()


@pytest.mark.asyncio
async def test_active_sessions_is_computed_when_explicitly_requested(mocker):
    count_mock = mocker.patch(
        f"{MODULE}.session_service.count_active_sessions", new_callable=AsyncMock, return_value=3
    )

    result = await current_user_handler.get_current_user("some-token", db=None, include_active_sessions=True)

    assert result["active_sessions"] == 3
    count_mock.assert_awaited_once_with(None, "user@example.com")


@pytest.mark.asyncio
async def test_active_sessions_is_zero_and_uncomputed_by_default(mocker):
    """The shared auth dependency behind nearly every protected route calls
    this same method without asking for active_sessions - GET /auth/me is
    the only caller that does - so by default this must skip the query
    entirely rather than pay for a count nothing reads."""
    count_mock = mocker.patch(f"{MODULE}.session_service.count_active_sessions", new_callable=AsyncMock)

    result = await current_user_handler.get_current_user("some-token", db=None)

    assert result["active_sessions"] == 0
    count_mock.assert_not_called()
