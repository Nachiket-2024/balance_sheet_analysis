# tests/backend/mystic_auth/unit/test_sentry_service_unit.py
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.mystic_auth.error_monitoring import sentry_service

MODULE = "backend.mystic_auth.error_monitoring.sentry_service"


def _fake_request(cookies: dict | None = None, method: str = "GET", path: str = "/users/me"):
    request = MagicMock()
    request.cookies = cookies or {}
    request.method = method
    request.url.path = path
    return request


def test_init_sentry_is_a_no_op_when_dsn_is_unset(mocker):
    # Default state for every clone of this template: error monitoring must
    # never crash startup, or make any SDK call, just because SENTRY_DSN
    # was never configured.
    mocker.patch(f"{MODULE}.settings.SENTRY_DSN", "")
    init_mock = mocker.patch(f"{MODULE}.sentry_sdk.init")

    sentry_service.init_sentry()

    init_mock.assert_not_called()


def test_init_sentry_initializes_the_sdk_when_dsn_is_set(mocker):
    mocker.patch(f"{MODULE}.settings.SENTRY_DSN", "https://examplePublicKey@o0.ingest.example.com/0")
    mocker.patch(f"{MODULE}.settings.SENTRY_ENVIRONMENT", "staging")
    init_mock = mocker.patch(f"{MODULE}.sentry_sdk.init")

    sentry_service.init_sentry()

    init_mock.assert_called_once()
    _, kwargs = init_mock.call_args
    assert kwargs["dsn"] == "https://examplePublicKey@o0.ingest.example.com/0"
    assert kwargs["environment"] == "staging"


def test_init_sentry_falls_back_to_environment_when_sentry_environment_unset(mocker):
    mocker.patch(f"{MODULE}.settings.SENTRY_DSN", "https://examplePublicKey@o0.ingest.example.com/0")
    mocker.patch(f"{MODULE}.settings.SENTRY_ENVIRONMENT", "")
    mocker.patch(f"{MODULE}.settings.ENVIRONMENT", "production")
    init_mock = mocker.patch(f"{MODULE}.sentry_sdk.init")

    sentry_service.init_sentry()

    _, kwargs = init_mock.call_args
    assert kwargs["environment"] == "production"


def test_init_sentry_does_not_raise_when_the_dsn_is_malformed(mocker):
    # Regression guard: sentry_sdk.init() raises (sentry_sdk.utils.BadDsn)
    # on a malformed DSN, and this function runs unguarded at import time in
    # main.py, before global_exception_handler exists to catch anything. A
    # typo in this optional, best-effort setting must never crash startup.
    # Uses the real sentry_sdk.init (not mocked) so this test would fail
    # again if the try/except around it were ever removed.
    mocker.patch(f"{MODULE}.settings.SENTRY_DSN", "not-a-valid-dsn-at-all")

    sentry_service.init_sentry()  # must not raise


def test_init_sentry_logs_a_warning_when_the_dsn_is_malformed(mocker):
    mocker.patch(f"{MODULE}.settings.SENTRY_DSN", "not-a-valid-dsn-at-all")
    warning_mock = mocker.patch(f"{MODULE}.startup_logger.warning")

    sentry_service.init_sentry()

    warning_mock.assert_called_once()


@pytest.mark.asyncio
async def test_capture_security_alert_emits_tagged_error_event(mocker):
    scope = MagicMock()
    scope_context = MagicMock()
    scope_context.__enter__.return_value = scope
    scope_context.__exit__.return_value = False
    mocker.patch(f"{MODULE}.sentry_sdk.new_scope", return_value=scope_context)
    capture_mock = mocker.patch(f"{MODULE}.sentry_sdk.capture_message")

    await sentry_service.capture_security_alert(
        "refresh_token_reuse_detected", {"scope": "account", "revocation_confirmed": False}
    )

    scope.set_level.assert_called_once_with("error")
    scope.set_tag.assert_called_once_with("security_event", "refresh_token_reuse_detected")
    scope.set_extra.assert_called_once()
    capture_mock.assert_called_once_with("Security alert: refresh_token_reuse_detected", level="error")


@pytest.mark.asyncio
async def test_capture_security_alert_posts_metadata_only_to_configured_webhook(mocker):
    mocker.patch(f"{MODULE}.settings.SECURITY_ALERT_WEBHOOK_URL", "https://alerts.example.test/security")
    mocker.patch(f"{MODULE}.settings.SECURITY_ALERT_WEBHOOK_TOKEN", "webhook-secret")
    client = mocker.AsyncMock()
    response = mocker.Mock()
    response.raise_for_status.return_value = None
    client.post.return_value = response
    async_client = mocker.patch(f"{MODULE}.httpx.AsyncClient")
    async_client.return_value.__aenter__.return_value = client
    mocker.patch(f"{MODULE}.sentry_sdk.new_scope")
    mocker.patch(f"{MODULE}.sentry_sdk.capture_message")

    await sentry_service.capture_security_alert("session_event_connection_limit_exceeded", {"ip_limit": 20})

    client.post.assert_awaited_once()
    _, kwargs = client.post.call_args
    assert kwargs["headers"]["authorization"] == "Bearer webhook-secret"
    assert kwargs["json"]["event_type"] == "session_event_connection_limit_exceeded"
    assert kwargs["json"]["metadata"] == {"ip_limit": 20}


@pytest.mark.asyncio
async def test_capture_exception_reports_without_a_request(mocker):
    capture_mock = mocker.patch(f"{MODULE}.sentry_sdk.capture_exception")
    set_user_mock = mocker.patch(f"{MODULE}.sentry_sdk.set_user")
    exc = ValueError("boom")

    await sentry_service.capture_exception(exc)

    capture_mock.assert_called_once_with(exc)
    set_user_mock.assert_not_called()


@pytest.mark.asyncio
async def test_capture_exception_attaches_user_email_from_a_valid_access_token(mocker):
    request = _fake_request(cookies={"access_token": "valid-token"})
    mocker.patch(
        f"{MODULE}.jwt_service.verify_token",
        new_callable=AsyncMock,
        return_value={"email": "user@example.com", "type": "access"},
    )
    capture_mock = mocker.patch(f"{MODULE}.sentry_sdk.capture_exception")
    set_user_mock = mocker.patch(f"{MODULE}.sentry_sdk.set_user")
    set_context_mock = mocker.patch(f"{MODULE}.sentry_sdk.set_context")
    exc = ValueError("boom")

    await sentry_service.capture_exception(exc, request=request)

    set_user_mock.assert_called_once_with({"email": "user@example.com"})
    set_context_mock.assert_called_once_with("request", {"method": "GET", "path": "/users/me"})
    capture_mock.assert_called_once_with(exc)


@pytest.mark.asyncio
async def test_capture_exception_omits_user_context_when_no_access_token_cookie(mocker):
    request = _fake_request(cookies={})
    verify_mock = mocker.patch(f"{MODULE}.jwt_service.verify_token", new_callable=AsyncMock)
    set_user_mock = mocker.patch(f"{MODULE}.sentry_sdk.set_user")
    mocker.patch(f"{MODULE}.sentry_sdk.capture_exception")
    mocker.patch(f"{MODULE}.sentry_sdk.set_context")

    await sentry_service.capture_exception(ValueError("boom"), request=request)

    verify_mock.assert_not_called()
    set_user_mock.assert_not_called()


@pytest.mark.asyncio
async def test_capture_exception_omits_user_context_when_access_token_fails_to_verify(mocker):
    # Expired/tampered/wrong-type access_token cookie: same "no user
    # context, but still capture the exception" outcome as no cookie at all.
    request = _fake_request(cookies={"access_token": "expired-or-invalid"})
    mocker.patch(f"{MODULE}.jwt_service.verify_token", new_callable=AsyncMock, return_value=None)
    capture_mock = mocker.patch(f"{MODULE}.sentry_sdk.capture_exception")
    set_user_mock = mocker.patch(f"{MODULE}.sentry_sdk.set_user")
    mocker.patch(f"{MODULE}.sentry_sdk.set_context")

    await sentry_service.capture_exception(ValueError("boom"), request=request)

    set_user_mock.assert_not_called()
    capture_mock.assert_called_once()


@pytest.mark.asyncio
async def test_watch_for_late_dsn_is_a_no_op_when_dsn_already_set(mocker):
    # The common case (compose's own ~10s bounded wait already succeeded);
    # must not re-poll or re-init for no reason. A real pathlib.Path
    # instance can't have its methods patched directly (C-level slots), so
    # the whole module-level object is swapped for a MagicMock instead.
    mocker.patch(f"{MODULE}.settings.SENTRY_DSN", "https://already-set@example.com/1")
    fake_file = mocker.patch(f"{MODULE}._BUGSINK_BACKEND_DSN_FILE", new=MagicMock())

    await sentry_service.watch_for_late_dsn()

    fake_file.exists.assert_not_called()


@pytest.mark.asyncio
async def test_watch_for_late_dsn_is_a_no_op_when_bugsink_is_not_configured(mocker):
    # No BUGSINK_SUPERUSER_EMAIL means Bugsink isn't part of this run at
    # all, so the DSN file will never appear; don't poll for it.
    mocker.patch(f"{MODULE}.settings.SENTRY_DSN", "")
    mocker.patch(f"{MODULE}.os.environ.get", return_value=None)
    fake_file = mocker.patch(f"{MODULE}._BUGSINK_BACKEND_DSN_FILE", new=MagicMock())

    await sentry_service.watch_for_late_dsn()

    fake_file.exists.assert_not_called()


@pytest.mark.asyncio
async def test_watch_for_late_dsn_picks_up_the_dsn_once_the_file_appears(mocker):
    # Simulates the actual fresh-boot race this exists for: Bugsink is
    # still migrating when this starts polling, and bugsink-seed writes the
    # file partway through.
    mocker.patch(f"{MODULE}.settings.SENTRY_DSN", "")
    mocker.patch(f"{MODULE}.os.environ.get", return_value="someone@example.com")
    fake_file = mocker.patch(f"{MODULE}._BUGSINK_BACKEND_DSN_FILE", new=MagicMock())
    fake_file.exists.side_effect = [False, False, True]
    fake_file.read_text.return_value = "export SENTRY_DSN=http://somekey@bugsink:8000/1\n"
    sleep_mock = mocker.patch(f"{MODULE}.asyncio.sleep", new_callable=AsyncMock)
    init_mock = mocker.patch(f"{MODULE}.init_sentry")

    await sentry_service.watch_for_late_dsn(poll_interval=2.0, timeout_seconds=300.0)

    assert sleep_mock.await_count == 2
    init_mock.assert_called_once()
    # settings.SENTRY_DSN was mutated so the (mocked, here) init_sentry()
    # would have picked up the newly-found DSN on a real call.
    assert sentry_service.settings.SENTRY_DSN == "http://somekey@bugsink:8000/1"


@pytest.mark.asyncio
async def test_watch_for_late_dsn_gives_up_after_timeout(mocker):
    mocker.patch(f"{MODULE}.settings.SENTRY_DSN", "")
    mocker.patch(f"{MODULE}.os.environ.get", return_value="someone@example.com")
    fake_file = mocker.patch(f"{MODULE}._BUGSINK_BACKEND_DSN_FILE", new=MagicMock())
    fake_file.exists.return_value = False
    mocker.patch(f"{MODULE}.asyncio.sleep", new_callable=AsyncMock)
    init_mock = mocker.patch(f"{MODULE}.init_sentry")
    info_mock = mocker.patch(f"{MODULE}.startup_logger.info")

    await sentry_service.watch_for_late_dsn(poll_interval=2.0, timeout_seconds=4.0)

    init_mock.assert_not_called()
    info_mock.assert_called_once()
    assert "Gave up waiting" in info_mock.call_args.args[0]


@pytest.mark.asyncio
async def test_watch_for_late_dsn_returns_without_crashing_on_malformed_file(mocker):
    # Defensive: a file present but not matching the expected
    # "export SENTRY_DSN=..." shape must not raise or loop forever.
    mocker.patch(f"{MODULE}.settings.SENTRY_DSN", "")
    mocker.patch(f"{MODULE}.os.environ.get", return_value="someone@example.com")
    fake_file = mocker.patch(f"{MODULE}._BUGSINK_BACKEND_DSN_FILE", new=MagicMock())
    fake_file.exists.return_value = True
    fake_file.read_text.return_value = "garbage, not the expected shape"
    init_mock = mocker.patch(f"{MODULE}.init_sentry")

    await sentry_service.watch_for_late_dsn()  # must not raise

    init_mock.assert_not_called()
