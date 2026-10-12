# tests/backend/app/test_main_global_exception_handler_unit.py
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.app.main import global_exception_handler

MODULE = "backend.app.main"


@pytest.mark.asyncio
async def test_global_exception_handler_reports_to_error_monitoring_and_returns_generic_500(mocker):
    # This handler runs before Starlette marks the exception "unhandled", so
    # sentry-sdk's auto-instrumentation never fires; capture_exception must be
    # called explicitly or nothing gets reported.
    capture_mock = mocker.patch(f"{MODULE}.capture_exception", new_callable=AsyncMock)
    request = MagicMock()
    request.url.path = "/users/me"
    exc = RuntimeError("something broke")

    response = await global_exception_handler(request, exc)

    capture_mock.assert_awaited_once_with(exc, request=request)
    assert response.status_code == 500
    # Clients never see exception internals: docs/mystic_auth/security/hardening-http.md#error-handling
    assert b"something broke" not in response.body
