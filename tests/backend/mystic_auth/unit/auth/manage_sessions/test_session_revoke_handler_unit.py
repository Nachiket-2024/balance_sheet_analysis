# DELETE /auth/sessions/{id} must report a real 503, not a false "Session
# revoked", when the underlying chain-version bump can't be confirmed
# (Valkey unreachable): session_service.revoke_one_session raises
# TokenVersionUnavailableError in that case.
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from backend.mystic_auth.auth.manage_sessions.session_revoke_handler import (
    session_revoke_handler,
)
from backend.mystic_auth.auth.token_logic.token_version_store import (
    TokenVersionUnavailableError,
)

MODULE = "backend.mystic_auth.auth.manage_sessions.session_revoke_handler"


def _target_session(chain_id="chain-2", user_id=1):
    return SimpleNamespace(id=2, chain_id=chain_id, user_id=user_id, revoked_at=None)


@pytest.mark.asyncio
async def test_revoke_session_returns_503_when_chain_bump_is_unconfirmed(mocker):
    mocker.patch(
        f"{MODULE}.current_user_handler.get_current_user",
        new_callable=AsyncMock, return_value={"email": "user@example.com"},
    )
    mocker.patch(f"{MODULE}.user_crud.get_by_email", new_callable=AsyncMock, return_value=SimpleNamespace(id=1))
    mocker.patch(f"{MODULE}.session_repository.get_by_id", new_callable=AsyncMock, return_value=_target_session())
    mocker.patch(f"{MODULE}.jwt_service.decode_payload", new_callable=AsyncMock, return_value=None)
    mocker.patch(
        f"{MODULE}.session_service.revoke_one_session",
        new_callable=AsyncMock, side_effect=TokenVersionUnavailableError("valkey down"),
    )
    audit_mock = mocker.patch(f"{MODULE}.log_security_event", new_callable=AsyncMock)

    with pytest.raises(HTTPException) as exc_info:
        await session_revoke_handler.revoke_session("access-token", None, 2, db=object())

    assert exc_info.value.status_code == 503
    assert exc_info.value.code == "SESSION_REVOCATION_UNAVAILABLE"
    # No false "revoked" audit entry when the revoke was never confirmed.
    audit_mock.assert_not_called()


@pytest.mark.asyncio
async def test_revoke_session_succeeds_on_a_confirmed_bump(mocker):
    session = _target_session()
    mocker.patch(
        f"{MODULE}.current_user_handler.get_current_user",
        new_callable=AsyncMock, return_value={"email": "user@example.com"},
    )
    mocker.patch(f"{MODULE}.user_crud.get_by_email", new_callable=AsyncMock, return_value=SimpleNamespace(id=1))
    mocker.patch(f"{MODULE}.session_repository.get_by_id", new_callable=AsyncMock, return_value=session)
    mocker.patch(f"{MODULE}.jwt_service.decode_payload", new_callable=AsyncMock, return_value=None)
    mocker.patch(f"{MODULE}.session_service.revoke_one_session", new_callable=AsyncMock, return_value=session)
    audit_mock = mocker.patch(f"{MODULE}.log_security_event", new_callable=AsyncMock)

    result = await session_revoke_handler.revoke_session("access-token", None, 2, db=object())

    assert result == {"message": "Session revoked"}
    audit_mock.assert_awaited_once()
