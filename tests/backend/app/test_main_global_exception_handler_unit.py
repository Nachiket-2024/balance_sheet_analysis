# tests/backend/app/test_main_global_exception_handler_unit.py
from unittest.mock import AsyncMock, MagicMock

import pytest
from backend.app.main import global_exception_handler

MODULE = "backend.app.main"


@pytest.mark.asyncio
async def test_global_exception_handler_reports_to_error_monitoring_and_returns_generic_500(mocker):
    # Regression guard: this handler is the ONE place every otherwise-
    # unhandled exception passes through, and it's also the only place
    # error_monitoring.sentry_service.capture_exception ever gets called
    # from (see that module's own docstring for why: this handler already
    # intercepts every exception before Starlette would consider it
    # "unhandled", which is what sentry-sdk's own automatic instrumentation
    # relies on; without this explicit call, nothing would ever be
    # reported at all).
    capture_mock = mocker.patch(f"{MODULE}.capture_exception", new_callable=AsyncMock)
    request = MagicMock()
    request.url.path = "/users/me"
    exc = RuntimeError("something broke")

    response = await global_exception_handler(request, exc)

    capture_mock.assert_awaited_once_with(exc, request=request)
    assert response.status_code == 500
    # The client never sees exception internals, see
    # docs/mystic_auth/security/hardening.md#error-handling.
    assert b"something broke" not in response.body
