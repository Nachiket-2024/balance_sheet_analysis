import traceback
from collections.abc import Awaitable, Callable
from functools import wraps
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse

from ...core.settings import settings
from ...logging.logging_config import get_logger
from ...redis.client import redis_client
from .client_ip import get_client_ip

logger = get_logger(__name__)


class RateLimiterService:
    """Enforces a max-requests-per-window rate limit, backed by Redis."""

    MAX_REQUESTS_PER_WINDOW: int = settings.MAX_REQUESTS_PER_WINDOW
    REQUEST_WINDOW_SECONDS: int = settings.REQUEST_WINDOW_SECONDS

    @staticmethod
    async def record_request(key: str) -> bool:
        try:
            # INCR creates the key at 0 before incrementing if it doesn't
            # already exist, and is atomic: unlike a separate GET-then-SET,
            # this can't let two concurrent requests both read the same
            # pre-increment count and both be admitted past the limit.
            new_count = await redis_client.incr(key)

            if new_count == 1:
                await redis_client.expire(key, RateLimiterService.REQUEST_WINDOW_SECONDS)

            return new_count <= RateLimiterService.MAX_REQUESTS_PER_WINDOW

        except Exception:
            logger.error("Error recording rate-limited request:\n%s", traceback.format_exc())
            return False

    @staticmethod
    async def reset_counter(key: str) -> None:
        try:
            await redis_client.delete(key)

        except Exception:
            logger.error("Error resetting rate limiter counter:\n%s", traceback.format_exc())

    def rate_limited(
        self,
        endpoint_name: str,
        account_key_func: Callable[[dict], str | None] | None = None,
    ) -> Callable[[Callable[..., Awaitable[Any]]], Callable[..., Awaitable[Any]]]:
        """
        account_key_func, if given, extracts an account identifier (e.g. email)
        from the endpoint's resolved keyword arguments, since FastAPI always calls the
        wrapped endpoint with its dependencies as kwargs, so this can pull
        straight from the parsed request body/params (e.g.
        `lambda kwargs: kwargs["payload"].email`). Pass None for endpoints where
        no account identifier is available before the handler runs (e.g.
        token-only routes). When supplied, it adds a per-account limit, keyed
        independently of IP: this closes the gap where an attacker spreads
        requests targeting one account across many source IPs specifically to
        stay under the per-IP threshold, which a per-IP-only limiter would never
        flag as abuse.
        """
        def decorator(func: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
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

                allowed = await self.record_request(ip_key)

                if not allowed:
                    return JSONResponse(
                        content={
                            "error": f"Too many {endpoint_name} attempts",
                            "code": "TOO_MANY_ATTEMPTS",
                            "params": {"endpoint": endpoint_name},
                        },
                        status_code=429
                    )

                if account_key_func is not None:
                    try:
                        account_value = account_key_func(kwargs)
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
                        account_allowed = await self.record_request(account_key)

                        if not account_allowed:
                            return JSONResponse(
                                content={
                                    "error": f"Too many {endpoint_name} attempts",
                                    "code": "TOO_MANY_ATTEMPTS",
                                    "params": {"endpoint": endpoint_name},
                                },
                                status_code=429
                            )

                return await func(*args, **kwargs)

            return wrapper

        return decorator


rate_limiter_service = RateLimiterService()
