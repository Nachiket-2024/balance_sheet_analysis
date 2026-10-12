import time
import traceback
from typing import Any

from ....core.settings import settings
from ....logging.logging_config import get_logger
from ....valkey.client import valkey_client
from .rate_limiter_service import RateLimiterService

logger = get_logger(__name__)
_NON_STRING_KEY_PREFIXES = frozenset({"session_event_leases"})
_GLOB_METACHARACTERS = ("\\", "*", "?", "[", "]")


def _escape_glob(value: str) -> str:
    """Backslash-escapes Valkey/Redis `SCAN MATCH` glob metacharacters so a
    caller-supplied filter (identifier, endpoint) can never widen or
    narrow the scan pattern beyond a literal substring match."""
    for char in _GLOB_METACHARACTERS:
        value = value.replace(char, f"\\{char}")
    return value


class RateLimitDashboardService:
    """Read/admin side of the rate limiter's Valkey keyspace, split out of
    RateLimiterService so that class stays focused on the hot path
    (record_request/rate_limited, called on every rate-limited request).
    Backs the admin Rate Limit Dashboard only."""

    @staticmethod
    def _effective_limit(endpoint_name: str, key_scope: str) -> int:
        """The real threshold behind one listed counter. Most counters
        RateLimiterService writes (record_request) share the global
        MAX_REQUESTS_PER_WINDOW, but an endpoint that passed its own
        max_requests/window_seconds to rate_limited(...) is tracked in
        ENDPOINT_OVERRIDES and reported here instead - otherwise the
        dashboard would show every such endpoint's counter against a
        threshold it doesn't actually enforce. list_active_limits also
        surfaces login_protection_service's login_lock:{email|ip}:*
        counters (see its own docstring), which enforce two further,
        unrelated thresholds."""
        if endpoint_name == "login_lock":
            return (
                settings.MAX_FAILED_LOGIN_ATTEMPTS_PER_IP
                if key_scope == "ip"
                else settings.MAX_FAILED_LOGIN_ATTEMPTS
            )
        override = RateLimiterService.ENDPOINT_OVERRIDES.get(endpoint_name)
        return override[0] if override else RateLimiterService.MAX_REQUESTS_PER_WINDOW

    @staticmethod
    async def reset_counter(key: str) -> None:
        # The same Valkey instance holds unrelated security-critical keys too
        # (token revocations, reset/verify tokens, oauth_state, ...).
        # Without this shape check, DELETE /rate-limits/{key} could delete
        # any key, e.g. un-revoking a token, just by passing it as the path
        # param. Only delete keys matching list_active_limits' own
        # <endpoint>:<ip|account|email>:<identifier> shape.
        parts = key.rsplit(":", 2)
        if not RateLimitDashboardService._is_rate_limit_key(key):
            return
        # Custom application endpoints may use the shared rate limiter without
        # being part of MysticAuth's built-in catalog. The structural shape is
        # the security boundary here: never accept arbitrary Valkey keys, but do
        # allow a valid endpoint namespace owned by the application.
        if not parts[0] or ":" in parts[0]:
            return

        try:
            await valkey_client.delete(key)

        except Exception:
            logger.error("Error resetting rate limiter counter:\n%s", traceback.format_exc())
            return

        # Without clearing the scan snapshot cache, the dashboard's
        # post-reset refetch could re-serve a stale snapshot still listing
        # this just-deleted key. Clears every cached pattern rather than
        # figuring out which ones this key could match; an admin-only,
        # low-QPS page can afford to lose the rest of the cache.
        RateLimitDashboardService._scan_snapshot_cache = {}

    # Upper bound on keys one list_active_limits call will walk for a
    # total/page. Keeps the dashboard on real numbered pages while capping
    # SCAN cost: production keyspace can run into the tens of thousands of
    # keys, and a capped walk on read beats a secondary index on every
    # write for an admin-only, low-QPS page.
    MAX_SCANNED_KEYS: int = 5000
    _SCAN_BATCH: int = 500

    # TTL-bound counters keep expiring/appearing, so two page requests
    # walking the keyspace moments apart can disagree on what exists (page
    # 2 could return rows beyond what page 1's total implied). Caching the
    # matched-key snapshot per filter pattern gives consecutive page
    # requests a consistent view to slice.
    _SCAN_SNAPSHOT_TTL_SECONDS: float = 5.0
    _scan_snapshot_cache: dict[str, tuple[float, list[str], bool]] = {}

    @staticmethod
    def _is_rate_limit_key(key: str) -> bool:
        parts = key.rsplit(":", 2)
        return (
            len(parts) == 3
            and parts[1] in ("ip", "account", "email")
            and parts[0] not in _NON_STRING_KEY_PREFIXES
        )

    @staticmethod
    async def list_active_limits(
        page: int = 1,
        page_size: int = 25,
        scope: str | None = None,
        endpoint: str | None = None,
        identifier: str | None = None,
        kind: str | None = None,
        sort_by: str = "endpoint",
        sort_dir: str = "asc",
    ) -> tuple[list[dict[str, Any]], int, bool]:
        """
        Powers the admin Rate Limit Dashboard. `scope`/`endpoint`/
        `identifier` filter via Valkey-side `MATCH`, not a Python filter
        after fetching everything. `identifier` matches as a substring.

        Walks the keyspace with bounded `SCAN` batches (never `KEYS`, which
        blocks Valkey) up to MAX_SCANNED_KEYS, reads the bounded snapshot, and
        sorts before slicing the requested page. This keeps sorting correct
        across pages without adding work to the request hot path.

        Returns (entries, total, truncated). `truncated` means the walk hit
        MAX_SCANNED_KEYS before exhausting the keyspace, so `total` is a
        floor, not exact; the caller should prompt narrowing the filters.
        """
        scope_segment = scope if scope in ("ip", "account", "email") else "*"
        identifier_segment = f"*{_escape_glob(identifier)}*" if identifier else "*"
        endpoint_segment = _escape_glob(endpoint) if endpoint else "*"
        pattern = f"{endpoint_segment}:{scope_segment}:{identifier_segment}"
        cache_key = f"{pattern}|{kind or 'all'}"

        now = time.monotonic()
        cached = RateLimitDashboardService._scan_snapshot_cache.get(cache_key)
        if cached is not None and now - cached[0] < RateLimitDashboardService._SCAN_SNAPSHOT_TTL_SECONDS:
            _, matched_keys, truncated = cached
        else:
            matched_keys = []
            truncated = False
            cursor = 0
            try:
                while True:
                    cursor, batch = await valkey_client.scan(
                        cursor=cursor, match=pattern, count=RateLimitDashboardService._SCAN_BATCH
                    )
                    # str() only satisfies valkey-py's bytes-by-default stubs;
                    # decode_responses=True makes this always a str already.
                    matched_keys.extend(str(key) for key in batch)
                    if len(matched_keys) >= RateLimitDashboardService.MAX_SCANNED_KEYS:
                        matched_keys = matched_keys[:RateLimitDashboardService.MAX_SCANNED_KEYS]
                        truncated = True
                        break
                    if cursor == 0:
                        break
            except Exception:
                logger.error("Error scanning rate limiter keys:\n%s", traceback.format_exc())
                return [], 0, False

            # When `scope` isn't given, the pattern's scope segment stays
            # "*" (Valkey globs can't express "one of ip|account|email"), so
            # the walk also matches unrelated two-colon keys elsewhere in
            # Valkey (e.g. the authz cache). Filter those out before
            # computing total/slicing, or a page could render empty on
            # non-rate-limit keys while a later page had real rows.
            matched_keys = [key for key in matched_keys if RateLimitDashboardService._is_rate_limit_key(key)]

            matched_keys.sort()
            # Opportunistically drop expired snapshots so the cache doesn't
            # grow unbounded across distinct filter combinations over time.
            RateLimitDashboardService._scan_snapshot_cache = {
                key: value
                for key, value in RateLimitDashboardService._scan_snapshot_cache.items()
                if now - value[0] < RateLimitDashboardService._SCAN_SNAPSHOT_TTL_SECONDS
            }
            RateLimitDashboardService._scan_snapshot_cache[cache_key] = (now, matched_keys, truncated)

        if kind == "login_lockouts":
            matched_keys = [key for key in matched_keys if key.rsplit(":", 2)[0] == "login_lock"]
        elif kind == "at_limit" and matched_keys:
            async with valkey_client.pipeline(transaction=False) as pipe:
                for key in matched_keys:
                    pipe.get(key)
                counts = await pipe.execute()
            matched_keys = [
                key for key, count_raw in zip(matched_keys, counts, strict=True)
                if count_raw is not None
                and int(count_raw) >= RateLimitDashboardService._effective_limit(key.rsplit(":", 2)[0], key.rsplit(":", 2)[1])
            ]

        if not matched_keys:
            return [], 0, truncated

        async with valkey_client.pipeline(transaction=False) as pipe:
            for key in matched_keys:
                pipe.get(key)
                pipe.ttl(key)
            results = await pipe.execute()

        entries: list[dict[str, Any]] = []
        for i, key in enumerate(matched_keys):
            count_raw, ttl = results[2 * i], results[2 * i + 1]
            # valkey_client is constructed with decode_responses=True (see
            # valkey/client.py), so this is always str at runtime; the cast
            # is only to satisfy the client library's bytes-by-default stubs.
            parts = str(key).rsplit(":", 2)
            if not RateLimitDashboardService._is_rate_limit_key(str(key)):
                # Shouldn't happen given the MATCH pattern above, but a key
                # that doesn't parse cleanly is skipped rather than shown
                # with garbage endpoint/identifier fields.
                continue
            endpoint_name, key_scope, identifier = parts
            entries.append({
                "key": key,
                "endpoint": endpoint_name,
                "scope": key_scope,
                "identifier": identifier,
                "count": int(count_raw) if count_raw is not None else 0,
                # login_protection_service.py's login_lock:{email|ip}:*
                # counters aren't rate_limiter_service's own - they're a
                # failed-attempt lockout with their own, different
                # thresholds, not RateLimiterService.MAX_REQUESTS_PER_WINDOW.
                "limit": RateLimitDashboardService._effective_limit(endpoint_name, key_scope),
                "resets_in_seconds": ttl if ttl is not None and ttl >= 0 else None,
            })

        if sort_by == "count":
            entries.sort(key=lambda entry: entry["count"], reverse=sort_dir == "desc")
        elif sort_by == "resets_at":
            with_expiry = [entry for entry in entries if entry["resets_in_seconds"] is not None]
            without_expiry = [entry for entry in entries if entry["resets_in_seconds"] is None]
            with_expiry.sort(key=lambda entry: entry["resets_in_seconds"], reverse=sort_dir == "desc")
            entries = with_expiry + without_expiry
        elif sort_by in {"endpoint", "scope", "identifier"}:
            entries.sort(key=lambda entry: str(entry[sort_by]).casefold(), reverse=sort_dir == "desc")

        total = len(entries)
        offset = max(0, page - 1) * page_size
        return entries[offset:offset + page_size], total, truncated

    @staticmethod
    async def summarize_active_limits() -> dict[str, Any]:
        """Summarize the bounded active-counter snapshot for dashboard tiles.

        This deliberately uses the same key-shape validation and scan cap as
        ``list_active_limits``. Counts are computed from Valkey values rather
        than the currently visible table page, while remaining bounded for
        production keyspaces.
        """
        now = time.monotonic()
        pattern = "*:*:*"
        cached = RateLimitDashboardService._scan_snapshot_cache.get(pattern)
        if cached is not None and now - cached[0] < RateLimitDashboardService._SCAN_SNAPSHOT_TTL_SECONDS:
            _, matched_keys, truncated = cached
        else:
            matched_keys = []
            truncated = False
            cursor = 0
            try:
                while True:
                    cursor, batch = await valkey_client.scan(
                        cursor=cursor, match=pattern, count=RateLimitDashboardService._SCAN_BATCH
                    )
                    matched_keys.extend(str(key) for key in batch)
                    if len(matched_keys) >= RateLimitDashboardService.MAX_SCANNED_KEYS:
                        matched_keys = matched_keys[:RateLimitDashboardService.MAX_SCANNED_KEYS]
                        truncated = True
                        break
                    if cursor == 0:
                        break
            except Exception:
                logger.error("Error scanning rate limiter summary:\n%s", traceback.format_exc())
                return {"total": 0, "at_limit": 0, "login_lockouts": 0, "by_endpoint": {}, "by_scope": {}, "truncated": False}

            matched_keys = [key for key in matched_keys if RateLimitDashboardService._is_rate_limit_key(key)]
            matched_keys.sort()
            RateLimitDashboardService._scan_snapshot_cache[pattern] = (now, matched_keys, truncated)

        if not matched_keys:
            return {"total": 0, "at_limit": 0, "login_lockouts": 0, "by_endpoint": {}, "by_scope": {}, "truncated": truncated}

        async with valkey_client.pipeline(transaction=False) as pipe:
            for key in matched_keys:
                pipe.get(key)
            values = await pipe.execute()

        by_endpoint: dict[str, int] = {}
        by_scope: dict[str, int] = {}
        at_limit = 0
        login_lockouts = 0
        for key, count_raw in zip(matched_keys, values, strict=True):
            endpoint_name, key_scope, _ = key.rsplit(":", 2)
            by_endpoint[endpoint_name] = by_endpoint.get(endpoint_name, 0) + 1
            by_scope[key_scope] = by_scope.get(key_scope, 0) + 1
            if endpoint_name == "login_lock":
                login_lockouts += 1
            if count_raw is not None and int(count_raw) >= RateLimitDashboardService._effective_limit(endpoint_name, key_scope):
                at_limit += 1

        return {
            "total": len(matched_keys),
            "at_limit": at_limit,
            "login_lockouts": login_lockouts,
            "by_endpoint": by_endpoint,
            "by_scope": by_scope,
            "truncated": truncated,
        }


rate_limit_dashboard_service = RateLimitDashboardService()
