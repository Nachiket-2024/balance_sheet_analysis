# tests/backend/mystic_auth/unit/test_authorization_dependency_unit.py
#
# Unit coverage for require_authorization: the FastAPI dependency factory
# every PBAC-protected route depends on. Called directly here the same way
# FastAPI injects its inner `dependency` function in real requests, with an
# explicit current_user dict and a fake Request, so these tests exercise
# the authorization decision (and context building) without needing a
# running app.
from unittest.mock import AsyncMock, MagicMock

import pytest
from backend.mystic_auth.authorization.dependencies.authorization_dependency import require_authorization
from fastapi import HTTPException

MODULE = "backend.mystic_auth.authorization.dependencies.authorization_dependency"


def _user(email="user@example.com") -> dict:
    return {"name": "Test User", "email": email, "role": "user"}


def _request(client_host="203.0.113.7"):
    request = MagicMock()
    request.client.host = client_host
    return request


@pytest.mark.asyncio
async def test_grants_access_and_returns_current_user_when_authorized(mocker):
    mocker.patch(f"{MODULE}.authorization_service.require", new_callable=AsyncMock)
    dependency = require_authorization("users:list_all", "users")

    result = await dependency(request=_request(), current_user=_user(), db=None)

    assert result["email"] == "user@example.com"


@pytest.mark.asyncio
async def test_propagates_403_from_the_authorization_service(mocker):
    mocker.patch(
        f"{MODULE}.authorization_service.require",
        new_callable=AsyncMock,
        side_effect=HTTPException(status_code=403, detail="Insufficient permissions"),
    )
    dependency = require_authorization("users:list_all", "users")

    with pytest.raises(HTTPException) as exc_info:
        await dependency(request=_request(), current_user=_user(), db=None)

    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_calls_the_authorization_service_with_the_declared_action_and_resource_type(mocker):
    require_mock = mocker.patch(f"{MODULE}.authorization_service.require", new_callable=AsyncMock)
    dependency = require_authorization("users:delete_any", "users")

    await dependency(request=_request(), current_user=_user("admin@example.com"), db="fake-db-session")

    require_mock.assert_awaited_once()
    kwargs = require_mock.await_args.kwargs
    assert kwargs["user_email"] == "admin@example.com"
    assert kwargs["action"] == "users:delete_any"
    assert kwargs["resource_type"] == "users"
    assert kwargs["db"] == "fake-db-session"


@pytest.mark.asyncio
async def test_builds_a_real_context_from_the_request_connection(mocker):
    """The dependency must derive ip_address/current_time itself (via
    build_authorization_context) from the actual request, never from
    anything client-suppliable, and pass it through to the service."""
    require_mock = mocker.patch(f"{MODULE}.authorization_service.require", new_callable=AsyncMock)
    dependency = require_authorization("users:list_all", "users")

    await dependency(request=_request(client_host="198.51.100.9"), current_user=_user(), db=None)

    context = require_mock.await_args.kwargs["context"]
    assert context["ip_address"] == "198.51.100.9"
    assert "current_time" in context
    assert context["security_context"] == {}


@pytest.mark.asyncio
async def test_missing_client_connection_yields_no_ip_address_not_a_crash(mocker):
    require_mock = mocker.patch(f"{MODULE}.authorization_service.require", new_callable=AsyncMock)
    dependency = require_authorization("users:list_all", "users")
    request = MagicMock()
    request.client = None

    await dependency(request=request, current_user=_user(), db=None)

    context = require_mock.await_args.kwargs["context"]
    assert context["ip_address"] is None
