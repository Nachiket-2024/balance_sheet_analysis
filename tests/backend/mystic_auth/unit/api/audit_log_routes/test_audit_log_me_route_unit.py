# Unit coverage for GET /authorization/audit-log/me, the self-service audit
# endpoint. Calls the route as a plain function (as FastAPI would), so this
# exercises the scoping logic without a running app or real DB.
from unittest.mock import AsyncMock

import pytest
from fastapi import Response

from backend.mystic_auth.api.pbac_routes.pbac_audit_log_routes import list_my_audit_log

MODULE = "backend.mystic_auth.api.pbac_routes.pbac_audit_log_routes"


@pytest.mark.asyncio
async def test_list_my_audit_log_scopes_to_caller_email(mocker):
    """Must return only the authenticated caller's own entries, without
    requiring policies:read, and must never accept or use any other
    user's email."""
    current_user = {"email": "caller@example.com", "name": "Caller"}
    expected_entries = [object(), object()]
    get_for_user_mock = mocker.patch(
        f"{MODULE}.authorization_audit_log_repository.get_for_user", new_callable=AsyncMock, return_value=expected_entries
    )
    mocker.patch(f"{MODULE}.authorization_audit_log_repository.count_for_user", new_callable=AsyncMock, return_value=2)

    result = await list_my_audit_log(
        response=Response(),
        limit=50,
        offset=10,
        action=None,
        resource_type=None,
        allowed=None,
        sort_by=None,
        sort_dir="desc",
        from_=None,
        to=None,
        current_user=current_user,
        db="fake-db",
    )

    get_for_user_mock.assert_awaited_once_with(
        "caller@example.com",
        "fake-db",
        limit=50,
        offset=10,
        action=None,
        resource_type=None,
        allowed=None,
        sort_by=None,
        sort_dir="desc",
        from_=None,
        to=None,
    )
    assert result == expected_entries


@pytest.mark.asyncio
async def test_list_my_audit_log_default_paging(mocker):
    current_user = {"email": "someone@example.com", "name": "Someone"}
    get_for_user_mock = mocker.patch(
        f"{MODULE}.authorization_audit_log_repository.get_for_user", new_callable=AsyncMock, return_value=[]
    )
    mocker.patch(f"{MODULE}.authorization_audit_log_repository.count_for_user", new_callable=AsyncMock, return_value=0)

    await list_my_audit_log(
        response=Response(),
        limit=100,
        offset=0,
        action=None,
        resource_type=None,
        allowed=None,
        sort_by=None,
        sort_dir="desc",
        from_=None,
        to=None,
        current_user=current_user,
        db="fake-db",
    )

    get_for_user_mock.assert_awaited_once_with(
        "someone@example.com",
        "fake-db",
        limit=100,
        offset=0,
        action=None,
        resource_type=None,
        allowed=None,
        sort_by=None,
        sort_dir="desc",
        from_=None,
        to=None,
    )


@pytest.mark.asyncio
async def test_list_my_audit_log_passes_field_filters_through(mocker):
    """Action/resource_type/allowed filters must reach the repository call
    unchanged, the same way limit/offset/sort already do."""
    current_user = {"email": "caller@example.com", "name": "Caller"}
    get_for_user_mock = mocker.patch(
        f"{MODULE}.authorization_audit_log_repository.get_for_user", new_callable=AsyncMock, return_value=[]
    )
    mocker.patch(f"{MODULE}.authorization_audit_log_repository.count_for_user", new_callable=AsyncMock, return_value=0)

    await list_my_audit_log(
        response=Response(),
        limit=50,
        offset=0,
        action="policies:read",
        resource_type="policies",
        allowed=False,
        sort_by="action",
        sort_dir="asc",
        from_=None,
        to=None,
        current_user=current_user,
        db="fake-db",
    )

    get_for_user_mock.assert_awaited_once_with(
        "caller@example.com",
        "fake-db",
        limit=50,
        offset=0,
        action="policies:read",
        resource_type="policies",
        allowed=False,
        sort_by="action",
        sort_dir="asc",
        from_=None,
        to=None,
    )
