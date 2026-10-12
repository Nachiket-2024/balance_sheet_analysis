"""Anti-enumeration and failure-path tests for password reset requests."""

from unittest.mock import AsyncMock

import pytest

from backend.mystic_auth.auth.password_reset_request.password_reset_request_handler import (
    PasswordResetRequestHandler,
)

MODULE = "backend.mystic_auth.auth.password_reset_request.password_reset_request_handler"


@pytest.mark.asyncio
async def test_existing_account_is_audited_as_success_without_exposing_details(mocker):
    handler = PasswordResetRequestHandler()
    mocker.patch.object(handler.password_reset_service, "send_reset_email", new_callable=AsyncMock, return_value=True)
    audit = mocker.patch(f"{MODULE}.log_security_event", new_callable=AsyncMock)

    response = await handler.handle_password_reset_request("user@example.com", db="db", request="request")

    assert response.status_code == 200
    assert b"If the email exists" in response.body
    assert audit.await_args.kwargs == {"user_email": "user@example.com", "success": True, "request": "request"}


@pytest.mark.asyncio
async def test_unknown_account_is_audited_without_recording_the_probed_email(mocker):
    handler = PasswordResetRequestHandler()
    mocker.patch.object(handler.password_reset_service, "send_reset_email", new_callable=AsyncMock, return_value=False)
    audit = mocker.patch(f"{MODULE}.log_security_event", new_callable=AsyncMock)

    response = await handler.handle_password_reset_request("unknown@example.com", db="db")

    assert response.status_code == 200
    assert "user_email" not in audit.await_args.kwargs
    assert audit.await_args.kwargs["success"] is False


@pytest.mark.asyncio
async def test_reset_service_failure_returns_generic_internal_error(mocker):
    handler = PasswordResetRequestHandler()
    mocker.patch.object(
        handler.password_reset_service,
        "send_reset_email",
        new_callable=AsyncMock,
        side_effect=RuntimeError("mail provider down"),
    )
    audit = mocker.patch(f"{MODULE}.log_security_event", new_callable=AsyncMock)

    response = await handler.handle_password_reset_request("user@example.com", db="db")

    assert response.status_code == 500
    assert b"INTERNAL_SERVER_ERROR" in response.body
    audit.assert_not_awaited()
