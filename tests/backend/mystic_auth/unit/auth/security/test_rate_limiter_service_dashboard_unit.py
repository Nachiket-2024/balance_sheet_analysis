# Unit coverage for RateLimitDashboardService.list_active_limits /
# reset_counter, the admin Rate Limit Dashboard's read/reset primitives.
# Patches valkey_client's individual methods directly rather than
# standing up a real Valkey, since these are pure request/response-shape
# tests (see test_rate_limit_routes_integration.py for the real-Valkey
# path).
from unittest.mock import AsyncMock

import pytest

from backend.mystic_auth.auth.security.rate_limiting.rate_limit_dashboard_service import (
    RateLimitDashboardService,
    rate_limit_dashboard_service,
)
from backend.mystic_auth.auth.security.rate_limiting.rate_limiter_service import (
    RateLimiterService,
)
from backend.mystic_auth.core.settings import settings

MODULE = "backend.mystic_auth.auth.security.rate_limiting.rate_limit_dashboard_service"


@pytest.fixture(autouse=True)
def _reset_scan_snapshot_cache():
    """list_active_limits caches its matched-key walk per filter pattern
    for _SCAN_SNAPSHOT_TTL_SECONDS so consecutive dashboard page requests
    get a consistent view to slice. Most tests here use the same default
    (unfiltered) pattern, so without clearing this class-level cache
    between tests, a later test could pick up an earlier test's mocked
    SCAN/pipeline results instead of its own."""
    RateLimitDashboardService._scan_snapshot_cache = {}
    yield
    RateLimitDashboardService._scan_snapshot_cache = {}


class _FakePipeline:
    """Duck-typed stand-in for valkey.asyncio.client.Pipeline: only used as
    an async context manager whose .get()/.ttl() queue commands and whose
    .execute() returns a pre-canned flat [count, ttl, count, ttl, ...]
    result list, matching list_active_limits' own GET/TTL-per-key pairing.
    """

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
    return mocker.patch(f"{MODULE}.valkey_client.scan", new_callable=AsyncMock, return_value=(next_cursor, keys))


def _patch_pipeline(mocker, results):
    return mocker.patch(f"{MODULE}.valkey_client.pipeline", return_value=_FakePipeline(results))


@pytest.mark.asyncio
async def test_list_active_limits_parses_ip_and_account_keys(mocker):
    # Single SCAN batch that already exhausts the keyspace (cursor back to
    # 0), covering the common case: one walk, no looping needed.
    _patch_scan(mocker, 0, ["login:ip:1.2.3.4", "login:account:victim@example.com"])
    # Keys are sorted for stable pagination order (see list_active_limits'
    # docstring), so "login:account:..." (a < i) is read first here even
    # though it appears second in the raw SCAN batch above.
    _patch_pipeline(mocker, ["1", -1, "3", 42])

    entries, total, truncated = await rate_limit_dashboard_service.list_active_limits()

    assert total == 2
    assert truncated is False
    assert entries == [
        {
            "key": "login:account:victim@example.com",
            "endpoint": "login",
            "scope": "account",
            "identifier": "victim@example.com",
            "count": 1,
            "limit": RateLimiterService.MAX_REQUESTS_PER_WINDOW,
            "resets_in_seconds": None,
        },
        {
            "key": "login:ip:1.2.3.4",
            "endpoint": "login",
            "scope": "ip",
            "identifier": "1.2.3.4",
            "count": 3,
            "limit": RateLimiterService.MAX_REQUESTS_PER_WINDOW,
            "resets_in_seconds": 42,
        },
    ]


@pytest.mark.asyncio
async def test_list_active_limits_reports_an_endpoint_override_not_the_global_limit(mocker):
    # password_reset_request here stands in for any endpoint that passed
    # its own max_requests/window_seconds to rate_limited(...) - the
    # dashboard must show the threshold actually enforced for it, not the
    # unrelated global default every other endpoint shares.
    RateLimiterService.ENDPOINT_OVERRIDES["password_reset_request"] = (5, 900)
    try:
        _patch_scan(mocker, 0, ["password_reset_request:ip:1.2.3.4"])
        _patch_pipeline(mocker, ["1", 900])

        entries, _, _ = await rate_limit_dashboard_service.list_active_limits()

        assert entries[0]["limit"] == 5
    finally:
        del RateLimiterService.ENDPOINT_OVERRIDES["password_reset_request"]


@pytest.mark.asyncio
async def test_list_active_limits_walks_multiple_scan_batches_until_cursor_zero(mocker):
    # A keyspace that spans more than one SCAN batch must be walked fully
    # (cursor chained through) before the total/page can be computed.
    scan_mock = mocker.patch(
        f"{MODULE}.valkey_client.scan",
        new_callable=AsyncMock,
        side_effect=[(11, ["login:ip:1.1.1.1"]), (0, ["login:ip:2.2.2.2"])],
    )
    _patch_pipeline(mocker, ["1", 10, "1", 10])

    entries, total, truncated = await rate_limit_dashboard_service.list_active_limits(page=1, page_size=1)

    assert scan_mock.await_count == 2
    assert total == 2
    assert truncated is False
    assert len(entries) == 1


@pytest.mark.asyncio
async def test_list_active_limits_truncates_at_max_scanned_keys(mocker):
    mocker.patch(f"{MODULE}.RateLimitDashboardService.MAX_SCANNED_KEYS", 2)
    scan_mock = _patch_scan(mocker, 99, ["login:ip:1.1.1.1", "login:ip:2.2.2.2", "login:ip:3.3.3.3"])
    _patch_pipeline(mocker, ["1", 10, "1", 10])

    entries, total, truncated = await rate_limit_dashboard_service.list_active_limits(page_size=10)

    scan_mock.assert_awaited_once()
    assert total == 2
    assert truncated is True
    assert len(entries) == 2


@pytest.mark.asyncio
async def test_list_active_limits_slices_the_requested_page(mocker):
    # Sorted key order ("login:account:..." < "login:ip:...") must be
    # stable across requests since a fresh walk's SCAN order isn't.
    _patch_scan(mocker, 0, ["login:ip:2.2.2.2", "login:account:a@example.com", "login:ip:1.1.1.1"])
    _patch_pipeline(mocker, ["1", 10, "1", 10, "1", 10])

    entries, total, _ = await rate_limit_dashboard_service.list_active_limits(page=2, page_size=1)

    assert total == 3
    assert len(entries) == 1
    assert entries[0]["key"] == "login:ip:1.1.1.1"


@pytest.mark.asyncio
async def test_list_active_limits_sorts_before_slicing_the_requested_page(mocker):
    _patch_scan(mocker, 0, [
        "login:ip:1.1.1.1",
        "signup:ip:2.2.2.2",
        "password_reset_request:ip:3.3.3.3",
    ])
    _patch_pipeline(mocker, ["1", 10, "9", 20, "4", 30])

    entries, total, _ = await rate_limit_dashboard_service.list_active_limits(
        page=1, page_size=1, sort_by="count", sort_dir="desc"
    )

    assert total == 3
    assert entries[0]["count"] == 9


@pytest.mark.asyncio
async def test_reset_counter_rejects_a_fabricated_rate_limit_key(mocker):
    delete_mock = mocker.patch(f"{MODULE}.valkey_client.delete", new_callable=AsyncMock)

    await rate_limit_dashboard_service.reset_counter("fabricated:not-a-rate-limit-scope:1.2.3.4")

    delete_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_list_active_limits_filters_by_scope_and_endpoint_via_match_pattern(mocker):
    # Filtering happens Valkey-side (the MATCH pattern), not by fetching
    # everything and filtering in Python: a narrowed query must actually
    # be cheaper, not just smaller.
    scan_mock = _patch_scan(mocker, 0, [])
    _patch_pipeline(mocker, [])

    await rate_limit_dashboard_service.list_active_limits(scope="ip", endpoint="login")

    scan_mock.assert_awaited_once_with(cursor=0, match="login:ip:*", count=rate_limit_dashboard_service._SCAN_BATCH)


@pytest.mark.asyncio
async def test_list_active_limits_filters_by_email_scope_via_match_pattern(mocker):
    # login_protection_service's login_lock:email:* counters are a real
    # scope value (see RateLimitEntry.scope on the frontend). The service
    # layer has always accepted it; it was only the route's Query pattern
    # that used to reject it (see
    # test_rate_limit_routes_integration.py's
    # test_scope_filter_accepts_email_scope).
    scan_mock = _patch_scan(mocker, 0, [])
    _patch_pipeline(mocker, [])

    await rate_limit_dashboard_service.list_active_limits(scope="email", endpoint="login_lock")

    scan_mock.assert_awaited_once_with(cursor=0, match="login_lock:email:*", count=rate_limit_dashboard_service._SCAN_BATCH)


@pytest.mark.asyncio
async def test_list_active_limits_filters_login_lockouts_as_a_server_side_view(mocker):
    _patch_scan(mocker, 0, ["login_lock:email:person@example.test", "login:ip:1.2.3.4"])
    _patch_pipeline(mocker, ["5", 60])

    entries, total, _ = await rate_limit_dashboard_service.list_active_limits(kind="login_lockouts")

    assert total == 1
    assert entries[0]["endpoint"] == "login_lock"


@pytest.mark.asyncio
async def test_list_active_limits_skips_unparseable_keys(mocker):
    _patch_scan(mocker, 0, ["not-a-rate-limit-key", "session_event_leases:account:hashed-user"])
    _patch_pipeline(mocker, ["1", 10])

    entries, _, _ = await rate_limit_dashboard_service.list_active_limits()

    assert entries == []


@pytest.mark.asyncio
async def test_reset_counter_rejects_non_string_session_lease_key(mocker):
    delete_mock = mocker.patch(f"{MODULE}.valkey_client.delete", new_callable=AsyncMock)

    await rate_limit_dashboard_service.reset_counter("session_event_leases:account:hashed-user")

    delete_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_list_active_limits_returns_empty_on_valkey_error(mocker):
    mocker.patch(f"{MODULE}.valkey_client.scan", side_effect=ConnectionError("valkey unreachable"))
    error_mock = mocker.patch(f"{MODULE}.logger.error")

    entries, total, truncated = await rate_limit_dashboard_service.list_active_limits()

    assert entries == []
    assert total == 0
    assert truncated is False
    error_mock.assert_called_once()


@pytest.mark.asyncio
async def test_reset_counter_deletes_the_key(mocker):
    delete_mock = mocker.patch(f"{MODULE}.valkey_client.delete", new_callable=AsyncMock)

    await rate_limit_dashboard_service.reset_counter("login:ip:1.2.3.4")

    delete_mock.assert_awaited_once_with("login:ip:1.2.3.4")


@pytest.mark.asyncio
async def test_summarize_active_limits_counts_total_at_limit_lockouts_and_dimensions(mocker):
    _patch_scan(mocker, 0, [
        "login:ip:1.2.3.4",
        "login_lock:email:person@example.test",
        "signup:account:acct-1",
    ])
    _patch_pipeline(mocker, [
        str(RateLimiterService.MAX_REQUESTS_PER_WINDOW),
        str(settings.MAX_FAILED_LOGIN_ATTEMPTS),
        "1",
    ])

    summary = await rate_limit_dashboard_service.summarize_active_limits()

    assert summary == {
        "total": 3,
        "at_limit": 2,
        "login_lockouts": 1,
        "by_endpoint": {"login": 1, "login_lock": 1, "signup": 1},
        "by_scope": {"ip": 1, "email": 1, "account": 1},
        "truncated": False,
    }


@pytest.mark.asyncio
async def test_reset_counter_deletes_an_account_scoped_key(mocker):
    delete_mock = mocker.patch(f"{MODULE}.valkey_client.delete", new_callable=AsyncMock)

    await rate_limit_dashboard_service.reset_counter("password_reset_request:account:user@example.com")

    delete_mock.assert_awaited_once_with("password_reset_request:account:user@example.com")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "key",
    [
        # Not a rate-limit key at all: e.g. a token-revocation entry
        # (jwt_service.py), which this endpoint must never be able to
        # delete regardless of who calls it.
        "revoked:some-jti-value",
        "password_reset:some-token",
        "verify:some-token",
        # Right number of separators, wrong middle segment.
        "login:region:1.2.3.4",
        # Too few/many colon-separated parts to be <endpoint>:<scope>:<id>.
        "login:ip",
        "login:ip:1.2.3.4:extra",
    ],
)
async def test_reset_counter_ignores_a_key_outside_the_rate_limiter_keyspace(mocker, key):
    delete_mock = mocker.patch(f"{MODULE}.valkey_client.delete", new_callable=AsyncMock)

    await rate_limit_dashboard_service.reset_counter(key)

    delete_mock.assert_not_awaited()
