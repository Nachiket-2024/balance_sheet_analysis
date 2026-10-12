# tests/backend/mystic_auth/unit/user_session/test_session_repository_unit.py
#
# Mocked-DB coverage that every "revoke" method on SessionRepository deletes
# the target row(s) outright instead of setting revoked_at (see the class's
# own docstring in session_repository.py for why), plus the new
# delete_expired_unrevoked sweep query. Real-DB end-to-end behavior (a
# revoked session actually disappears from GET /auth/sessions, logout/
# logout-all delete the right rows) is covered separately in
# tests/backend/mystic_auth/integration/user_session/test_session_row_cleanup_integration.py,
# same unit/integration split as the rest of this test suite.
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.mystic_auth.user_session.session_model import UserSession
from backend.mystic_auth.user_session.session_repository import SessionRepository


def _make_session(**overrides) -> UserSession:
    defaults = {
        "id": 1,
        "user_id": 1,
        "current_jti": "jti-1",
        "chain_id": "chain-1",
        "expires_at": datetime.now(UTC) + timedelta(days=1),
        "revoked_at": None,
    }
    defaults.update(overrides)
    return UserSession(**defaults)


def _fake_result(*, scalar=None, rowcount=None):
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value=scalar)
    result.rowcount = rowcount
    return result


@pytest.mark.asyncio
async def test_revoke_by_id_deletes_the_row_and_returns_a_snapshot(mocker):
    # Deletes via db.execute(delete(...)), not db.delete(instance) - see
    # session_repository.py's own comment on why (avoids a SAWarning under
    # a legitimate concurrent-revoke race). db.delete must stay untouched.
    session = _make_session(id=5, user_id=7)
    mocker.patch.object(SessionRepository, "get_by_id", new=AsyncMock(return_value=session))
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_fake_result(rowcount=1))

    result = await SessionRepository.revoke_by_id(db, session_id=5, user_id=7)

    db.execute.assert_awaited_once()
    db.delete.assert_not_awaited()
    db.commit.assert_awaited_once()
    assert result is not None
    assert result.id == 5
    assert result.user_id == 7


@pytest.mark.asyncio
async def test_revoke_by_id_is_a_noop_when_the_row_belongs_to_a_different_user(mocker):
    session = _make_session(id=5, user_id=7)
    mocker.patch.object(SessionRepository, "get_by_id", new=AsyncMock(return_value=session))
    db = AsyncMock()

    result = await SessionRepository.revoke_by_id(db, session_id=5, user_id=999)

    db.execute.assert_not_awaited()
    db.commit.assert_not_awaited()
    assert result is None


@pytest.mark.asyncio
async def test_revoke_by_id_is_a_noop_when_the_row_does_not_exist(mocker):
    mocker.patch.object(SessionRepository, "get_by_id", new=AsyncMock(return_value=None))
    db = AsyncMock()

    result = await SessionRepository.revoke_by_id(db, session_id=5, user_id=7)

    db.execute.assert_not_awaited()
    assert result is None


@pytest.mark.asyncio
async def test_revoke_by_jti_deletes_the_row_and_returns_a_snapshot(mocker):
    session = _make_session(current_jti="jti-1")
    mocker.patch.object(SessionRepository, "get_by_jti", new=AsyncMock(return_value=session))
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_fake_result(rowcount=1))

    result = await SessionRepository.revoke_by_jti(db, jti="jti-1")

    db.execute.assert_awaited_once()
    db.delete.assert_not_awaited()
    db.commit.assert_awaited_once()
    assert result is not None
    assert result.current_jti == "jti-1"


@pytest.mark.asyncio
async def test_revoke_by_jti_is_a_noop_when_the_row_does_not_exist(mocker):
    mocker.patch.object(SessionRepository, "get_by_jti", new=AsyncMock(return_value=None))
    db = AsyncMock()

    result = await SessionRepository.revoke_by_jti(db, jti="jti-1")

    db.execute.assert_not_awaited()
    assert result is None


@pytest.mark.asyncio
async def test_revoke_by_chain_id_deletes_the_matching_row(mocker):
    session = _make_session(id=9, chain_id="chain-9")
    db = AsyncMock()
    # First execute is the SELECT lookup by chain_id, second is the DELETE
    # by primary key.
    db.execute = AsyncMock(side_effect=[_fake_result(scalar=session), _fake_result(rowcount=1)])

    result = await SessionRepository.revoke_by_chain_id(db, chain_id="chain-9")

    assert db.execute.await_count == 2
    db.delete.assert_not_awaited()
    db.commit.assert_awaited_once()
    assert result is not None
    assert result.chain_id == "chain-9"


@pytest.mark.asyncio
async def test_revoke_by_chain_id_is_a_noop_when_no_row_matches(mocker):
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_fake_result(scalar=None))

    result = await SessionRepository.revoke_by_chain_id(db, chain_id="chain-9")

    assert db.execute.await_count == 1
    db.delete.assert_not_awaited()
    assert result is None


@pytest.mark.asyncio
async def test_revoke_all_for_user_deletes_every_row_and_returns_the_count():
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_fake_result(rowcount=3))

    result = await SessionRepository.revoke_all_for_user(db, user_id=7)

    db.commit.assert_awaited_once()
    assert result == 3


@pytest.mark.asyncio
async def test_revoke_all_for_user_returns_zero_when_rowcount_is_none():
    # Some DB-API drivers report rowcount as None rather than 0 for an
    # affected-nothing DELETE; `or 0` must normalize that.
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_fake_result(rowcount=None))

    result = await SessionRepository.revoke_all_for_user(db, user_id=7)

    assert result == 0


@pytest.mark.asyncio
async def test_revoke_all_for_user_except_chain_returns_the_count():
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_fake_result(rowcount=2))

    result = await SessionRepository.revoke_all_for_user_except_chain(db, user_id=7, exempt_chain_id="chain-1")

    db.commit.assert_awaited_once()
    assert result == 2


@pytest.mark.asyncio
async def test_delete_expired_unrevoked_returns_the_deleted_count():
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_fake_result(rowcount=40))

    cutoff = datetime.now(UTC) - timedelta(hours=1)
    result = await SessionRepository.delete_expired_unrevoked(db, before=cutoff)

    db.commit.assert_awaited_once()
    assert result == 40


@pytest.mark.asyncio
async def test_delete_expired_unrevoked_returns_zero_when_nothing_matched():
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_fake_result(rowcount=0))

    cutoff = datetime.now(UTC) - timedelta(hours=1)
    result = await SessionRepository.delete_expired_unrevoked(db, before=cutoff)

    assert result == 0
