# tests/backend/mystic_auth/unit/test_security_audit_service_unit.py
#
# Unit coverage for audit.services.security_audit_service.log_security_event
# : the single choke point every auth handler calls to persist a security
# audit row. Mirrors AuthorizationService._log_decision's own contract: a
# logging failure must never raise, since the real action it describes has
# already happened (or failed) regardless of whether the audit write
# succeeds.
from unittest.mock import AsyncMock, MagicMock

import pytest
from backend.mystic_auth.audit_log import audit_log_service
from backend.mystic_auth.audit_log.audit_log_service import (
    LOGIN_SUCCESS,
    log_security_event,
)

MODULE = "backend.mystic_auth.audit_log.audit_log_service"


@pytest.mark.asyncio
async def test_log_security_event_writes_expected_fields(mocker):
    create_entry_mock = mocker.patch(
        f"{MODULE}.audit_log_repository.create_entry", new_callable=AsyncMock
    )

    request = MagicMock()
    request.client.host = "203.0.113.5"
    request.headers.get.return_value = "pytest-agent"
    request.state.request_id = "req-123"

    await log_security_event(
        LOGIN_SUCCESS,
        db="fake-db",
        user_email="user@example.com",
        success=True,
        request=request,
        metadata={"foo": "bar"},
    )

    create_entry_mock.assert_awaited_once_with(
        {
            "user_email": "user@example.com",
            "event_type": LOGIN_SUCCESS,
            "success": True,
            "ip_address": "203.0.113.5",
            "user_agent": "pytest-agent",
            "request_id": "req-123",
            "event_metadata": {"foo": "bar"},
        },
        "fake-db",
    )


@pytest.mark.asyncio
async def test_log_security_event_without_request_omits_request_context(mocker):
    create_entry_mock = mocker.patch(
        f"{MODULE}.audit_log_repository.create_entry", new_callable=AsyncMock
    )

    await log_security_event(LOGIN_SUCCESS, db="fake-db", user_email="user@example.com", success=True)

    written = create_entry_mock.await_args.args[0]
    assert written["ip_address"] is None
    assert written["user_agent"] is None
    assert written["request_id"] is None


@pytest.mark.asyncio
async def test_log_security_event_never_raises_when_repository_fails(mocker):
    mocker.patch(
        f"{MODULE}.audit_log_repository.create_entry",
        new_callable=AsyncMock,
        side_effect=RuntimeError("db is down"),
    )
    warning_mock = mocker.patch.object(audit_log_service.logger, "warning")

    # Must not raise despite the repository failure
    await log_security_event(LOGIN_SUCCESS, db="fake-db", user_email="user@example.com", success=True)

    warning_mock.assert_called_once()


# ---------------------------- metadata redaction (defense-in-depth) ----------------------------
#
# No current call site passes sensitive data in metadata (all 11 call sites
# only ever pass emails/counts) : this is a structural backstop against a
# future call site accidentally doing so, not a fix for an existing leak.

@pytest.mark.asyncio
async def test_log_security_event_redacts_sensitive_looking_metadata_keys(mocker):
    create_entry_mock = mocker.patch(
        f"{MODULE}.audit_log_repository.create_entry", new_callable=AsyncMock
    )

    await log_security_event(
        LOGIN_SUCCESS,
        db="fake-db",
        user_email="user@example.com",
        success=True,
        metadata={
            "password": "hunter2",
            "new_password_hash": "$argon2id$...",
            "refresh_token": "eyJ...",
            "auth_cookie": "abc123",
            "client_secret": "shh",
            "sessions_revoked": 3,
            "deleted_by": "admin@example.com",
        },
    )

    written_metadata = create_entry_mock.await_args.args[0]["event_metadata"]
    assert written_metadata["password"] == "[REDACTED]"
    assert written_metadata["new_password_hash"] == "[REDACTED]"
    assert written_metadata["refresh_token"] == "[REDACTED]"
    assert written_metadata["auth_cookie"] == "[REDACTED]"
    assert written_metadata["client_secret"] == "[REDACTED]"
    # Non-sensitive keys pass through unchanged.
    assert written_metadata["sessions_revoked"] == 3
    assert written_metadata["deleted_by"] == "admin@example.com"


@pytest.mark.asyncio
async def test_log_security_event_handles_none_metadata(mocker):
    create_entry_mock = mocker.patch(
        f"{MODULE}.audit_log_repository.create_entry", new_callable=AsyncMock
    )

    await log_security_event(LOGIN_SUCCESS, db="fake-db", user_email="user@example.com", success=True)

    assert create_entry_mock.await_args.args[0]["event_metadata"] is None
