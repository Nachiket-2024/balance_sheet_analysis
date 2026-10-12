"""Edge-case coverage for the rate-limit dashboard service."""

from unittest.mock import AsyncMock

import pytest

from backend.mystic_auth.auth.security.rate_limiting.rate_limit_dashboard_service import (
    RateLimitDashboardService,
    rate_limit_dashboard_service,
)
from backend.mystic_auth.auth.security.rate_limiting.rate_limiter_service import (
    RateLimiterService,
)

MODULE = "backend.mystic_auth.auth.security.rate_limiting.rate_limit_dashboard_service"


@pytest.fixture(autouse=True)
def _reset_scan_snapshot_cache():
    RateLimitDashboardService._scan_snapshot_cache = {}
    yield
    RateLimitDashboardService._scan_snapshot_cache = {}


class _FakePipeline:
    def __init__(self, results):
        self._results = results

    def get(self, key):
        pass

    def ttl(self, key):
        pass

    async def execute(self):
        return self._results

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False


def _patch_scan(mocker, next_cursor, keys):
    return mocker.patch(
        f"{MODULE}.valkey_client.scan",
        new_callable=AsyncMock,
        return_value=(next_cursor, keys),
    )


@pytest.mark.asyncio
async def test_reset_counter_rejects_nested_endpoint_and_logs_delete_failure(mocker):
    delete_mock = mocker.patch(f"{MODULE}.valkey_client.delete", new_callable=AsyncMock)

    await rate_limit_dashboard_service.reset_counter("nested:endpoint:ip:1.2.3.4")
    delete_mock.assert_not_awaited()

    delete_mock.side_effect = RuntimeError("valkey unavailable")
    error_mock = mocker.patch(f"{MODULE}.logger.error")
    await rate_limit_dashboard_service.reset_counter("login:ip:1.2.3.4")
    error_mock.assert_called_once()


@pytest.mark.asyncio
async def test_list_active_limits_filters_at_limit_and_sorts_by_expiry(mocker):
    _patch_scan(mocker, 0, ["login:ip:1.2.3.4", "signup:ip:2.2.2.2"])
    pipeline_mock = mocker.patch(
        f"{MODULE}.valkey_client.pipeline",
        side_effect=[
            _FakePipeline([str(RateLimiterService.MAX_REQUESTS_PER_WINDOW), "0"]),
            _FakePipeline(["5", -1, "9", 30]),
        ],
    )

    entries, total, _ = await rate_limit_dashboard_service.list_active_limits(
        kind="at_limit", sort_by="resets_at", sort_dir="desc"
    )

    assert total == 1
    assert entries[0]["key"] == "login:ip:1.2.3.4"
    assert pipeline_mock.call_count == 2


@pytest.mark.asyncio
async def test_summarize_active_limits_returns_empty_on_scan_error(mocker):
    mocker.patch(f"{MODULE}.valkey_client.scan", side_effect=ConnectionError("valkey unavailable"))
    error_mock = mocker.patch(f"{MODULE}.logger.error")

    summary = await rate_limit_dashboard_service.summarize_active_limits()

    assert summary == {
        "total": 0,
        "at_limit": 0,
        "login_lockouts": 0,
        "by_endpoint": {},
        "by_scope": {},
        "truncated": False,
    }
    error_mock.assert_called_once()


@pytest.mark.asyncio
async def test_summarize_active_limits_reports_empty_snapshot(mocker):
    _patch_scan(mocker, 0, [])

    summary = await rate_limit_dashboard_service.summarize_active_limits()

    assert summary["total"] == 0
    assert summary["by_endpoint"] == {}


@pytest.mark.asyncio
async def test_list_active_limits_escapes_valkey_glob_metacharacters_in_filters(mocker):
    scan_mock = _patch_scan(mocker, 0, [])
    mocker.patch(f"{MODULE}.valkey_client.pipeline", return_value=_FakePipeline([]))

    await rate_limit_dashboard_service.list_active_limits(
        scope="ip",
        endpoint=r"login[*]?" + "\\",
        identifier=r"a[*]?" + "\\" + "b",
    )

    scan_mock.assert_awaited_once_with(
        cursor=0,
        match=r"login\[\*\]\?\\:ip:*a\[\*\]\?\\b*",
        count=rate_limit_dashboard_service._SCAN_BATCH,
    )
