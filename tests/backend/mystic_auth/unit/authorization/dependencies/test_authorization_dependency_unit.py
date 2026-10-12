# Unit coverage for require_authorization: the FastAPI dependency factory every
# PBAC-protected route depends on. Called directly with an explicit current_user
# dict and a fake Request (the same way FastAPI injects it in real requests), so
# these tests exercise the authorization decision without needing a running app.
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from backend.mystic_auth.authorization.dependencies.authorization_dependency import (
    require_any_authorization,
    require_authorization,
)

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
    dependency = require_authorization("users:deactivate_any", "users")

    await dependency(request=_request(), current_user=_user("admin@example.com"), db="fake-db-session")

    require_mock.assert_awaited_once()
    kwargs = require_mock.await_args.kwargs
    assert kwargs["user_email"] == "admin@example.com"
    assert kwargs["action"] == "users:deactivate_any"
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


# require_any_authorization: OR of multiple (action, resource_type) checks,
# used by CATALOG_READ_DEPENDENCY (permission_route_dependencies.py) so a
# route that's a genuine prerequisite of more than one independent feature
# doesn't have to pick just one action to gate behind.
class TestRequireAnyAuthorization:
    """Each candidate is probed via the non-logging authorize_detailed() first
    (a denied candidate must never write a spurious audit row); only the one
    that actually succeeds is re-checked via authorize() to log the decision."""

    @pytest.mark.asyncio
    async def test_grants_access_when_the_first_check_is_authorized(self, mocker):
        detailed_mock = mocker.patch(
            f"{MODULE}.authorization_service.authorize_detailed",
            new_callable=AsyncMock, return_value=MagicMock(allowed=True),
        )
        authorize_mock = mocker.patch(f"{MODULE}.authorization_service.authorize", new_callable=AsyncMock)
        dependency = require_any_authorization([("permissions:read", "permissions"), ("policies:create", "policies")])

        result = await dependency(request=_request(), current_user=_user(), db=None)

        assert result["email"] == "user@example.com"
        # Short-circuits: the second candidate is never probed once the
        # first already grants access, and only that one winning candidate
        # is (re-)checked via the logging authorize() call.
        detailed_mock.assert_awaited_once()
        authorize_mock.assert_awaited_once()
        assert authorize_mock.await_args.kwargs["action"] == "permissions:read"

    @pytest.mark.asyncio
    async def test_grants_access_when_only_a_later_check_is_authorized(self, mocker):
        async def fake_authorize_detailed(*, action, **_kwargs):
            return MagicMock(allowed=(action == "policies:create"))

        mocker.patch(
            f"{MODULE}.authorization_service.authorize_detailed",
            new_callable=AsyncMock, side_effect=fake_authorize_detailed,
        )
        authorize_mock = mocker.patch(f"{MODULE}.authorization_service.authorize", new_callable=AsyncMock)
        dependency = require_any_authorization([("permissions:read", "permissions"), ("policies:create", "policies")])

        result = await dependency(request=_request(), current_user=_user(), db=None)

        assert result["email"] == "user@example.com"
        # Only the actually-successful candidate gets logged.
        authorize_mock.assert_awaited_once()
        assert authorize_mock.await_args.kwargs["action"] == "policies:create"

    @pytest.mark.asyncio
    async def test_denies_access_with_403_when_every_check_fails(self, mocker):
        mocker.patch(
            f"{MODULE}.authorization_service.authorize_detailed",
            new_callable=AsyncMock, return_value=MagicMock(allowed=False),
        )
        authorize_mock = mocker.patch(f"{MODULE}.authorization_service.authorize", new_callable=AsyncMock)
        dependency = require_any_authorization([("permissions:read", "permissions"), ("policies:create", "policies")])

        with pytest.raises(HTTPException) as exc_info:
            await dependency(request=_request(), current_user=_user(), db=None)

        assert exc_info.value.status_code == 403
        # No candidate ever succeeded, so nothing gets (re-)checked/logged.
        authorize_mock.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_checks_each_candidate_with_its_own_action_and_resource_type(self, mocker):
        detailed_mock = mocker.patch(
            f"{MODULE}.authorization_service.authorize_detailed",
            new_callable=AsyncMock, return_value=MagicMock(allowed=False),
        )
        mocker.patch(f"{MODULE}.authorization_service.authorize", new_callable=AsyncMock)
        dependency = require_any_authorization([("permissions:read", "permissions"), ("policies:create", "policies")])

        with pytest.raises(HTTPException):
            await dependency(request=_request(), current_user=_user("admin@example.com"), db="fake-db-session")

        calls = detailed_mock.await_args_list
        assert len(calls) == 2
        assert calls[0].kwargs["action"] == "permissions:read"
        assert calls[0].kwargs["resource_type"] == "permissions"
        assert calls[1].kwargs["action"] == "policies:create"
        assert calls[1].kwargs["resource_type"] == "policies"
        for call in calls:
            assert call.kwargs["user_email"] == "admin@example.com"
            assert call.kwargs["db"] == "fake-db-session"
