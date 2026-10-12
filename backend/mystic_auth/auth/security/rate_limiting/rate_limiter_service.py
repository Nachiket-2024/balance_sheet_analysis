import inspect
import traceback
from collections.abc import Awaitable, Callable
from functools import wraps
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse, RedirectResponse

from ....core.settings import settings
from ....logging.logging_config import get_logger
from ....valkey.client import valkey_client
from ..client_ip import get_client_ip

logger = get_logger(__name__)


class RateLimiterService:
    """Enforces a max-requests-per-window rate limit, backed by Valkey."""

    MAX_REQUESTS_PER_WINDOW: int = settings.MAX_REQUESTS_PER_WINDOW
    REQUEST_WINDOW_SECONDS: int = settings.REQUEST_WINDOW_SECONDS

    # endpoint_name -> (max_requests, window_seconds) for every endpoint
    # that overrode the global default via rate_limited(...)'s max_requests/
    # window_seconds. Populated once at import time, when each decorated
    # route's module loads - read by RateLimitDashboardService so the admin
    # dashboard reports the threshold actually enforced, not always the
    # global one. An endpoint that never overrides is simply absent here.
    ENDPOINT_OVERRIDES: dict[str, tuple[int, int]] = {}
    REGISTERED_ENDPOINTS: set[str] = set()

    @staticmethod
    async def record_request(
        key: str, max_requests: int | None = None, window_seconds: int | None = None
    ) -> bool:
        """max_requests/window_seconds default to the global settings; pass
        both explicitly for a caller (e.g. rate_limited(...)'s wrapper) that
        enforces its own per-endpoint override instead."""
        max_requests = max_requests if max_requests is not None else RateLimiterService.MAX_REQUESTS_PER_WINDOW
        window_seconds = (
            window_seconds if window_seconds is not None else RateLimiterService.REQUEST_WINDOW_SECONDS
        )
        try:
            # INCR creates the key at 0 before incrementing if it doesn't
            # already exist, and is atomic: unlike a separate GET-then-SET,
            # this can't let two concurrent requests both read the same
            # pre-increment count and both be admitted past the limit.
            new_count = await valkey_client.incr(key)

            if new_count == 1:
                await valkey_client.expire(key, window_seconds)

            return new_count <= max_requests

        except Exception:
            logger.error("Error recording rate-limited request:\n%s", traceback.format_exc())
            return False

    def rate_limited(
        self,
        endpoint_name: str,
        account_key_func: Callable[[dict], str | None | Awaitable[str | None]] | None = None,
        redirect_url: str | None = None,
        max_requests: int | None = None,
        window_seconds: int | None = None,
    ) -> Callable[[Callable[..., Awaitable[Any]]], Callable[..., Awaitable[Any]]]:
        """
        max_requests/window_seconds override the global
        MAX_REQUESTS_PER_WINDOW/REQUEST_WINDOW_SECONDS defaults for this one
        endpoint - e.g. a rarely-hit route like password-reset-request
        wants a tighter limit than the high-traffic login route shares by
        default. Give both together or neither; either given alone still
        falls back to the global default for the other.

        account_key_func, if given, extracts an account identifier (e.g. email)
        from the endpoint's resolved keyword arguments, since FastAPI always calls the
        wrapped endpoint with its dependencies as kwargs, so this can pull
        straight from the parsed request body/params (e.g.
        `lambda kwargs: kwargs["payload"].email`). May be sync or async (the
        wrapper below awaits the result iff it's awaitable) - a token-only
        route (e.g. get_current_user, logout) has no such field to read
        synchronously, only an encoded access_token cookie, so its
        account_key_func decodes that instead (see
        auth_routes.py's `_access_token_account_key`, backed by
        jwt_service.decode_payload - real signature+expiry verification, just
        skipping the revocation lookup verify_token also does, so this stays
        a local CPU-bound decode with no extra Valkey round trip). Pass None
        for endpoints with no account identifier available by either means.
        When supplied, it adds a per-account limit, keyed independently of
        IP: this closes the gap where an attacker spreads requests targeting
        one account across many source IPs specifically to stay under the
        per-IP threshold, which a per-IP-only limiter would never flag as
        abuse.

        redirect_url, if given, is used instead of the default JSON 429 body
        when the limit is exceeded. Only meaningful for endpoints that are
        themselves a top-level browser navigation (e.g. the OAuth2 routes,
        which always return a RedirectResponse) - a raw JSON body has
        nowhere sensible to render there.
        """
        effective_max = max_requests if max_requests is not None else self.MAX_REQUESTS_PER_WINDOW
        effective_window = window_seconds if window_seconds is not None else self.REQUEST_WINDOW_SECONDS
        self.REGISTERED_ENDPOINTS.add(endpoint_name)
        if max_requests is not None or window_seconds is not None:
            self.ENDPOINT_OVERRIDES[endpoint_name] = (effective_max, effective_window)

        def decorator(func: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
            def _limit_exceeded_response() -> JSONResponse | RedirectResponse:
                if redirect_url:
                    return RedirectResponse(url=redirect_url)
                return JSONResponse(
                    content={
                        "error": f"Too many {endpoint_name} attempts",
                        "code": "TOO_MANY_ATTEMPTS",
                        "params": {"endpoint": endpoint_name},
                    },
                    status_code=429,
                )

            @wraps(func)
            async def wrapper(*args: Any, **kwargs: Any) -> Any:
                request: Request | None = None

                for arg in args:
                    if isinstance(arg, Request):
                        request = arg
                        break

                if not request:
                    request = kwargs.get("request")

                ip_address = (get_client_ip(request) if request else None) or "unknown"

                ip_key = f"{endpoint_name}:ip:{ip_address}"

                allowed = await self.record_request(ip_key, effective_max, effective_window)

                if not allowed:
                    return _limit_exceeded_response()

                if account_key_func is not None:
                    try:
                        account_value = account_key_func(kwargs)
                        if inspect.isawaitable(account_value):
                            account_value = await account_value
                    except Exception:
                        # Extraction failing (missing/malformed field) shouldn't
                        # break the request, just skip the account-level check.
                        # Logged because a silent skip here means per-account
                        # brute-force protection quietly stops applying.
                        logger.warning(
                            "account_key_func failed for endpoint '%s'; "
                            "per-account rate limiting skipped for this request:\n%s",
                            endpoint_name,
                            traceback.format_exc(),
                        )
                        account_value = None

                    if account_value:
                        account_key = f"{endpoint_name}:account:{account_value}"
                        account_allowed = await self.record_request(account_key, effective_max, effective_window)

                        if not account_allowed:
                            return _limit_exceeded_response()

                return await func(*args, **kwargs)

            return wrapper

        return decorator


rate_limiter_service = RateLimiterService()
