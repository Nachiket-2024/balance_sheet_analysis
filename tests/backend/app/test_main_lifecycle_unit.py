from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.app import main


def test_shutdown_relay_chains_previous_signal_handlers(mocker):
    previous = MagicMock()
    mocker.patch.object(main.signal, "getsignal", return_value=previous)
    install = mocker.patch.object(main.signal, "signal")
    notify = mocker.patch.object(main, "signal_session_events_shutdown")

    main._relay_shutdown_signal_to_session_events()

    assert install.call_count == 2
    for call in install.call_args_list:
        handler = call.args[1]
        handler(call.args[0], object())

    assert notify.call_count == 2
    assert previous.call_count == 2


def test_shutdown_relay_skips_installation_when_signal_lookup_is_unavailable(mocker):
    mocker.patch.object(main.signal, "getsignal", side_effect=ValueError)
    install = mocker.patch.object(main.signal, "signal")

    main._relay_shutdown_signal_to_session_events()

    install.assert_not_called()


def test_shutdown_relay_stops_when_signal_installation_is_unavailable(mocker):
    mocker.patch.object(main.signal, "getsignal", return_value=None)
    mocker.patch.object(main.signal, "signal", side_effect=ValueError)

    main._relay_shutdown_signal_to_session_events()


@pytest.mark.asyncio
async def test_lifespan_opens_and_closes_worker_and_clients(mocker):
    watcher = MagicMock()
    def capture_task(coroutine):
        coroutine.close()
        return watcher

    create_task = mocker.patch.object(main.asyncio, "create_task", side_effect=capture_task)
    mocker.patch.object(main, "watch_for_late_dsn", new_callable=AsyncMock)
    open_mock = mocker.patch.object(main.procrastinate_app, "open_async", new_callable=AsyncMock)
    close_mock = mocker.patch.object(main.procrastinate_app, "close_async", new_callable=AsyncMock)
    from sqlalchemy.ext.asyncio import AsyncEngine

    dispose_mock = mocker.patch.object(AsyncEngine, "dispose", new_callable=AsyncMock)
    valkey_close = mocker.patch.object(main.valkey_client, "aclose", new_callable=AsyncMock)

    async with main.lifespan(MagicMock()):
        open_mock.assert_awaited_once()

    create_task.assert_called_once()
    watcher.cancel.assert_called_once()
    dispose_mock.assert_awaited_once()
    valkey_close.assert_awaited_once()
    close_mock.assert_awaited_once()
