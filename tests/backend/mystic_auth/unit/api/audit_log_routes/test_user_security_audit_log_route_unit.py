# Unit coverage for GET /audit/security-log/users/{user_email}, the admin
# counterpart to /security-log/me (see test_audit_log_me_route_unit.py's
# matching pattern) - scoping logic exercised as a plain function call, no
# running app or real DB.
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from fastapi import Response

from backend.mystic_auth.api.audit_log_routes.audit_log_routes import (
    get_login_trend,
    get_my_login_trend,
    list_user_security_audit_log,
)

MODULE = "backend.mystic_auth.api.audit_log_routes.audit_log_routes"


@pytest.mark.asyncio
async def test_global_login_trend_passes_exact_range_to_repository(mocker):
    trend = [{"date": "2026-01-01", "success": 1, "failure": 0}]
    get_trend_mock = mocker.patch(
        f"{MODULE}.audit_log_repository.get_login_trend", new_callable=AsyncMock, return_value=trend
    )
    from_ = datetime(2026, 1, 1, tzinfo=UTC)
    to = datetime(2026, 1, 3, tzinfo=UTC)

    result = await get_login_trend(
        days=90,
        search="caller@example.com",
        from_=from_,
        to=to,
        current_user={"email": "operator@example.com"},
        db="fake-db",
    )

    get_trend_mock.assert_awaited_once_with(
        "fake-db", days=90, search="caller@example.com", from_=from_, to=to
    )
    assert result == trend


@pytest.mark.asyncio
async def test_my_login_trend_remains_caller_scoped_with_exact_range(mocker):
    get_trend_mock = mocker.patch(
        f"{MODULE}.audit_log_repository.get_login_trend", new_callable=AsyncMock, return_value=[]
    )
    from_ = datetime(2026, 1, 1, tzinfo=UTC)
    to = datetime(2026, 1, 3, tzinfo=UTC)

    await get_my_login_trend(
        days=90,
        from_=from_,
        to=to,
        current_user={"email": "caller@example.com"},
        db="fake-db",
    )

    get_trend_mock.assert_awaited_once_with(
        "fake-db", days=90, user_email="caller@example.com", from_=from_, to=to
    )


@pytest.mark.asyncio
async def test_list_user_security_audit_log_scopes_to_target_email(mocker):
    """Must query the repository for the path's user_email, not the caller's
    own - this is the admin route, unlike /security-log/me."""
    current_user = {"email": "admin@example.com", "name": "Admin"}
    expected_entries = [object(), object()]
    get_for_user_mock = mocker.patch(
        f"{MODULE}.audit_log_repository.get_for_user", new_callable=AsyncMock, return_value=expected_entries
    )
    mocker.patch(f"{MODULE}.audit_log_repository.count_for_user", new_callable=AsyncMock, return_value=2)

    result = await list_user_security_audit_log(
        user_email="target@example.com",
        response=Response(),
        limit=50,
        offset=0,
        event_type=None,
        ip_address=None,
        success=None,
        sort_by=None,
        sort_dir="desc",
        from_=None,
        to=None,
        current_user=current_user,
        db="fake-db",
    )

    get_for_user_mock.assert_awaited_once_with(
        "target@example.com",
        "fake-db",
        limit=50,
        offset=0,
        event_type=None,
        ip_address=None,
        success=None,
        sort_by=None,
        sort_dir="desc",
        from_=None,
        to=None,
    )
    assert result == expected_entries


@pytest.mark.asyncio
async def test_list_user_security_audit_log_passes_access_change_filter_through(mocker):
    """The "access_change" event_type alias (see audit_log_repository.py's
    _apply_filters) must reach the repository call unchanged - it's the
    repository, not this route, that expands it to the real event types."""
    current_user = {"email": "admin@example.com", "name": "Admin"}
    get_for_user_mock = mocker.patch(
        f"{MODULE}.audit_log_repository.get_for_user", new_callable=AsyncMock, return_value=[]
    )
    mocker.patch(f"{MODULE}.audit_log_repository.count_for_user", new_callable=AsyncMock, return_value=0)

    await list_user_security_audit_log(
        user_email="target@example.com",
        response=Response(),
        limit=5,
        offset=0,
        event_type="access_change",
        ip_address=None,
        success=None,
        sort_by=None,
        sort_dir="desc",
        from_=None,
        to=None,
        current_user=current_user,
        db="fake-db",
    )

    get_for_user_mock.assert_awaited_once_with(
        "target@example.com",
        "fake-db",
        limit=5,
        offset=0,
        event_type="access_change",
        ip_address=None,
        success=None,
        sort_by=None,
        sort_dir="desc",
        from_=None,
        to=None,
    )


@pytest.mark.asyncio
async def test_list_user_security_audit_log_sets_total_count_header(mocker):
    """X-Total-Count must reflect count_for_user's result for the SAME
    target user_email and filters, mirroring list_my_security_audit_log's
    identical pattern - a caller paging through results needs a total that
    matches what it's actually paging through."""
    current_user = {"email": "admin@example.com", "name": "Admin"}
    mocker.patch(f"{MODULE}.audit_log_repository.get_for_user", new_callable=AsyncMock, return_value=[])
    count_mock = mocker.patch(f"{MODULE}.audit_log_repository.count_for_user", new_callable=AsyncMock, return_value=17)
    response = Response()

    await list_user_security_audit_log(
        user_email="target@example.com",
        response=response,
        limit=5,
        offset=0,
        event_type="access_change",
        ip_address=None,
        success=None,
        sort_by=None,
        sort_dir="desc",
        from_=None,
        to=None,
        current_user=current_user,
        db="fake-db",
    )

    count_mock.assert_awaited_once_with(
        "target@example.com", "fake-db", event_type="access_change", ip_address=None, success=None, from_=None, to=None
    )
    assert response.headers["X-Total-Count"] == "17"
