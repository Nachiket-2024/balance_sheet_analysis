# tests/backend/mystic_auth/unit/user_session/test_session_service_unit.py
#
# Valkey fail-open regression coverage for revoke_session_on_logout (plain
# Logout) and revoke_one_session (Manage Sessions "End session"): a chain-
# version bump that can't be confirmed (Valkey unreachable) must never look
# identical to a real revoke. See docs/mystic_auth/concerns/README.md's
# now-resolved "Valkey outage failure modes are inconsistent" entry.
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.mystic_auth.auth.token_logic.token_version_store import (
    TokenVersionUnavailableError,
)
from backend.mystic_auth.user_session.session_service import SessionService

MODULE = "backend.mystic_auth.user_session.session_service"


def _fake_session(chain_id="chain-1", revoked_at=None, user_id=1):
    return SimpleNamespace(id=1, chain_id=chain_id, revoked_at=revoked_at, user_id=user_id)


@pytest.mark.asyncio
async def test_revoke_session_on_logout_returns_true_on_a_confirmed_bump(mocker):
    mocker.patch(
        f"{MODULE}.session_repository.get_by_jti", new_callable=AsyncMock, return_value=_fake_session()
    )
    mocker.patch(f"{MODULE}.jwt_service.bump_chain_version", new_callable=AsyncMock, return_value=True)
    mocker.patch(f"{MODULE}.session_repository.revoke_by_jti", new_callable=AsyncMock)
    mocker.patch(f"{MODULE}.publish_session_revoked", new_callable=AsyncMock)

    result = await SessionService.revoke_session_on_logout(db=object(), jti="jti-1", email="user@example.com")

    assert result is True


@pytest.mark.asyncio
async def test_revoke_session_on_logout_returns_false_when_bump_is_unconfirmed(mocker):
    mocker.patch(
        f"{MODULE}.session_repository.get_by_jti", new_callable=AsyncMock, return_value=_fake_session()
    )
    mocker.patch(f"{MODULE}.jwt_service.bump_chain_version", new_callable=AsyncMock, return_value=False)
    revoke_by_jti_mock = mocker.patch(f"{MODULE}.session_repository.revoke_by_jti", new_callable=AsyncMock)

    result = await SessionService.revoke_session_on_logout(db=object(), jti="jti-1", email="user@example.com")

    assert result is False
    # The Postgres row must be left untouched: marking it revoked while the
    # real Valkey-backed version stayed unbumped would make the row lie
    # about the token actually being dead.
    revoke_by_jti_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_revoke_session_on_logout_returns_true_when_nothing_to_revoke(mocker):
    mocker.patch(f"{MODULE}.session_repository.get_by_jti", new_callable=AsyncMock, return_value=None)

    result = await SessionService.revoke_session_on_logout(db=object(), jti="jti-1", email="user@example.com")

    assert result is True


@pytest.mark.asyncio
async def test_revoke_one_session_raises_when_chain_bump_is_unconfirmed(mocker):
    mocker.patch(
        f"{MODULE}.user_crud.get_by_email", new_callable=AsyncMock, return_value=SimpleNamespace(id=1)
    )
    mocker.patch(
        f"{MODULE}.session_repository.get_by_id", new_callable=AsyncMock, return_value=_fake_session(user_id=1)
    )
    mocker.patch(f"{MODULE}.jwt_service.bump_chain_version", new_callable=AsyncMock, return_value=False)
    revoke_by_id_mock = mocker.patch(f"{MODULE}.session_repository.revoke_by_id", new_callable=AsyncMock)

    with pytest.raises(TokenVersionUnavailableError):
        await SessionService.revoke_one_session(db=object(), email="user@example.com", session_id=1)

    # The Postgres row must be left untouched on an unconfirmed bump - see
    # session_revoke_handler.py, which turns this into a 503 rather than a
    # false "Session revoked".
    revoke_by_id_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_revoke_one_session_succeeds_on_a_confirmed_bump(mocker):
    mocker.patch(
        f"{MODULE}.user_crud.get_by_email", new_callable=AsyncMock, return_value=SimpleNamespace(id=1)
    )
    session = _fake_session(user_id=1)
    mocker.patch(f"{MODULE}.session_repository.get_by_id", new_callable=AsyncMock, return_value=session)
    mocker.patch(f"{MODULE}.jwt_service.bump_chain_version", new_callable=AsyncMock, return_value=True)
    mocker.patch(f"{MODULE}.session_repository.revoke_by_id", new_callable=AsyncMock, return_value=session)
    mocker.patch(f"{MODULE}.publish_session_revoked", new_callable=AsyncMock)

    result = await SessionService.revoke_one_session(db=object(), email="user@example.com", session_id=1)

    assert result is session


@pytest.mark.asyncio
async def test_create_session_persists_client_metadata_and_notifies(mocker):
    create_mock = mocker.patch(f"{MODULE}.session_repository.create", new_callable=AsyncMock)
    mocker.patch(f"{MODULE}.get_client_ip", return_value="198.51.100.10")
    mocker.patch(f"{MODULE}.resolve_city_country", return_value=("Sydney", "Australia"))
    notify_mock = mocker.patch(f"{MODULE}.publish_session_created", new_callable=AsyncMock)
    request = MagicMock()
    request.headers.get.return_value = "browser/1.0"

    await SessionService.create_session(
        db=object(), user_id=4, jti="jti-new", chain_id="chain-new", exp=1_800_000_000,
        request=request, email="user@example.com",
    )

    create_mock.assert_awaited_once()
    assert create_mock.await_args.args[:4] == (create_mock.await_args.args[0], 4, "jti-new", "chain-new")
    assert create_mock.await_args.args[5:] == ("browser/1.0", "198.51.100.10", "Sydney", "Australia")
    notify_mock.assert_awaited_once_with("user@example.com")


@pytest.mark.asyncio
async def test_create_session_does_nothing_without_database(mocker):
    create_mock = mocker.patch(f"{MODULE}.session_repository.create", new_callable=AsyncMock)

    await SessionService.create_session(None, 1, "jti", "chain", 1_800_000_000, None, "user@example.com")

    create_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_rotate_session_backfills_missing_legacy_row(mocker):
    mocker.patch(f"{MODULE}.session_repository.rotate", new_callable=AsyncMock, return_value=None)
    mocker.patch(f"{MODULE}.user_crud.get_by_email", new_callable=AsyncMock, return_value=SimpleNamespace(id=9))
    create_mock = mocker.patch(f"{MODULE}.session_repository.create", new_callable=AsyncMock)
    mocker.patch(f"{MODULE}.get_client_ip", return_value="203.0.113.5")
    mocker.patch(f"{MODULE}.resolve_city_country", return_value=(None, None))
    request = MagicMock()
    request.headers.get.return_value = "mobile/2"

    await SessionService.rotate_session(object(), "old", "new", "chain", 1_800_000_000, "user@example.com", request)

    create_mock.assert_awaited_once()
    assert create_mock.await_args.args[1:4] == (9, "new", "chain")
    assert create_mock.await_args.args[5:] == ("mobile/2", "203.0.113.5", None, None)


@pytest.mark.asyncio
async def test_revoke_all_sessions_uses_exempt_chain_when_requested(mocker):
    mocker.patch(f"{MODULE}.user_crud.get_by_email", new_callable=AsyncMock, return_value=SimpleNamespace(id=7))
    except_mock = mocker.patch(
        f"{MODULE}.session_repository.revoke_all_for_user_except_chain", new_callable=AsyncMock
    )

    await SessionService.revoke_all_sessions(object(), "user@example.com", exempt_chain_id="keep-chain")

    except_mock.assert_awaited_once_with(except_mock.await_args.args[0], 7, "keep-chain")


@pytest.mark.asyncio
async def test_list_and_count_return_empty_for_unknown_user(mocker):
    mocker.patch(f"{MODULE}.user_crud.get_by_email", new_callable=AsyncMock, return_value=None)

    assert await SessionService.list_sessions(object(), "missing@example.com") == []
    assert await SessionService.count_active_sessions(object(), "missing@example.com") == 0


@pytest.mark.asyncio
async def test_revoke_chain_is_fail_open_on_repository_error(mocker):
    mocker.patch(
        f"{MODULE}.session_repository.revoke_by_chain_id", new_callable=AsyncMock,
        side_effect=RuntimeError("database unavailable"),
    )

    await SessionService.revoke_chain(object(), "chain-1")

    # Session tracking must never turn a successful authentication flow into
    # an outage when the auxiliary row cannot be updated.


@pytest.mark.asyncio
async def test_rotate_session_and_chain_skip_without_database(mocker):
    rotate_mock = mocker.patch(f"{MODULE}.session_repository.rotate", new_callable=AsyncMock)
    chain_mock = mocker.patch(f"{MODULE}.session_repository.rotate_by_chain_id", new_callable=AsyncMock)

    await SessionService.rotate_session(None, "old", "new", "chain", 1_800_000_000)
    await SessionService.rotate_session_by_chain(None, "chain", "new", 1_800_000_000)

    rotate_mock.assert_not_awaited()
    chain_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_rotate_session_handles_repository_failure_without_raising(mocker):
    mocker.patch(
        f"{MODULE}.session_repository.rotate",
        new_callable=AsyncMock,
        side_effect=RuntimeError("database unavailable"),
    )
    warning_mock = mocker.patch(f"{MODULE}.logger.warning")

    await SessionService.rotate_session(object(), "old", "new", "chain", 1_800_000_000)

    warning_mock.assert_called_once()


@pytest.mark.asyncio
async def test_rotate_session_by_chain_backfills_legacy_row(mocker):
    mocker.patch(f"{MODULE}.session_repository.rotate_by_chain_id", new_callable=AsyncMock, return_value=None)
    mocker.patch(f"{MODULE}.user_crud.get_by_email", new_callable=AsyncMock, return_value=SimpleNamespace(id=12))
    create_mock = mocker.patch(f"{MODULE}.session_repository.create", new_callable=AsyncMock)
    mocker.patch(f"{MODULE}.get_client_ip", return_value="198.51.100.20")
    mocker.patch(f"{MODULE}.resolve_city_country", return_value=("Melbourne", "Australia"))
    request = MagicMock()
    request.headers.get.return_value = "browser/2.0"

    await SessionService.rotate_session_by_chain(
        object(), "chain", "new", 1_800_000_000, "user@example.com", request
    )

    create_mock.assert_awaited_once()
    assert create_mock.await_args.args[1:4] == (12, "new", "chain")


@pytest.mark.asyncio
async def test_revoke_all_sessions_handles_missing_user_and_database(mocker):
    revoke_mock = mocker.patch(f"{MODULE}.session_repository.revoke_all_for_user", new_callable=AsyncMock)
    mocker.patch(f"{MODULE}.user_crud.get_by_email", new_callable=AsyncMock, return_value=None)

    await SessionService.revoke_all_sessions(object(), "missing@example.com")
    await SessionService.revoke_all_sessions(None, "user@example.com")

    revoke_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_revoke_one_session_returns_none_for_missing_owner_or_target(mocker):
    mocker.patch(f"{MODULE}.user_crud.get_by_email", new_callable=AsyncMock, return_value=None)
    assert await SessionService.revoke_one_session(object(), "missing@example.com", 1) is None

    mocker.patch(f"{MODULE}.user_crud.get_by_email", new_callable=AsyncMock, return_value=SimpleNamespace(id=2))
    mocker.patch(f"{MODULE}.session_repository.get_by_id", new_callable=AsyncMock, return_value=None)
    assert await SessionService.revoke_one_session(object(), "user@example.com", 1) is None
