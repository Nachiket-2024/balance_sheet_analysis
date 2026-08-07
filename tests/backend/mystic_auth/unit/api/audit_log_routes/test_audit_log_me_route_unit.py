# tests/backend/mystic_auth/unit/api/audit_log_routes/test_audit_log_me_route_unit.py
#
# Unit coverage for GET /authorization/audit-log/me, the self-service audit
# endpoint ("User self-service audit access"). Called directly as
# a plain function, the same way FastAPI would inject it, so this exercises
# the scoping logic without needing a running app or real DB.
from unittest.mock import AsyncMock

import pytest
from backend.mystic_auth.api.pbac_routes.pbac_audit_log_routes import list_my_audit_log
from fastapi import Response

MODULE = "backend.mystic_auth.api.pbac_routes.pbac_audit_log_routes"


@pytest.mark.asyncio
async def test_list_my_audit_log_scopes_to_caller_email(mocker):
    """Must return only the authenticated caller's own entries, without
    requiring policies:read, and must never accept or use any other
    user's email."""
    current_user = {"email": "caller@example.com", "name": "Caller"}
    expected_entries = [object(), object()]
    get_for_user_mock = mocker.patch(
        f"{MODULE}.audit_log_repository.get_for_user", new_callable=AsyncMock, return_value=expected_entries
    )
    mocker.patch(f"{MODULE}.audit_log_repository.count_for_user", new_callable=AsyncMock, return_value=2)

    result = await list_my_audit_log(
        response=Response(),
        limit=50,
        offset=10,
        action=None,
        resource_type=None,
        allowed=None,
        sort_by=None,
        sort_dir="desc",
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
    )
    assert result == expected_entries


@pytest.mark.asyncio
async def test_list_my_audit_log_default_paging(mocker):
    current_user = {"email": "someone@example.com", "name": "Someone"}
    get_for_user_mock = mocker.patch(
        f"{MODULE}.audit_log_repository.get_for_user", new_callable=AsyncMock, return_value=[]
    )
    mocker.patch(f"{MODULE}.audit_log_repository.count_for_user", new_callable=AsyncMock, return_value=0)

    await list_my_audit_log(
        response=Response(),
        limit=100,
        offset=0,
        action=None,
        resource_type=None,
        allowed=None,
        sort_by=None,
        sort_dir="desc",
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
    )


@pytest.mark.asyncio
async def test_list_my_audit_log_passes_field_filters_through(mocker):
    """Action/resource_type/allowed filters must reach the repository call
    unchanged, the same way limit/offset/sort already do."""
    current_user = {"email": "caller@example.com", "name": "Caller"}
    get_for_user_mock = mocker.patch(
        f"{MODULE}.audit_log_repository.get_for_user", new_callable=AsyncMock, return_value=[]
    )
    mocker.patch(f"{MODULE}.audit_log_repository.count_for_user", new_callable=AsyncMock, return_value=0)

    await list_my_audit_log(
        response=Response(),
        limit=50,
        offset=0,
        action="policies:read",
        resource_type="policies",
        allowed=False,
        sort_by="action",
        sort_dir="asc",
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
    )
