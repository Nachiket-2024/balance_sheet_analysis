import traceback

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ...auth.refresh_token_logic.refresh_token_service import refresh_token_service
from ...auth.security.login_protection_service import login_protection_service
from ...auth.security.rate_limiting.rate_limiter_service import rate_limiter_service
from ...auth.token_logic.jwt_service import jwt_service
from ...core.errors import AppError
from ...logging.logging_config import get_logger

# Resolves the real client IP, honoring X-Forwarded-For only from a configured
# trusted reverse proxy (see auth/security/client_ip.py).
from ..security.client_ip import get_client_ip
from ..token_logic.token_cookie_handler import token_cookie_handler
from ..token_logic.token_schema import TokenPairResponseSchema

logger = get_logger(__name__)


class RefreshTokenHandler:
    """Validates and rotates refresh tokens, with rate limiting and brute-force protection."""

    @staticmethod
    async def handle_refresh_tokens(
        request: Request, refresh_token: str | None, db: AsyncSession | None = None
    ) -> JSONResponse:
        try:
            # Same 401 outcome as an invalid token, so a client can't distinguish
            # "never had a session" from "had one that's now invalid" purely from
            # this response.
            if not refresh_token:
                raise AppError(
                    status_code=401,
                    code="INVALID_OR_REVOKED_REFRESH_TOKEN",
                    detail="Invalid or revoked refresh token"
                )

            client_ip = get_client_ip(request) or "unknown"

            # These must live in distinct key namespaces: rate_limiter_service
            # and login_protection_service each maintain their own independent
            # counter/TTL semantics (a sliding request count vs. a failure
            # count), and sharing one key made every refresh call, successful or
            # not, count towards the 5-attempt lockout threshold: a handful of
            # legitimate token rotations from one IP could trip "too many failed
            # attempts" with zero actual failures.
            rate_key = f"refresh:ratelimit:ip:{client_ip}"
            lock_key = f"refresh:lockout:ip:{client_ip}"

            # Account-level lockout dimension, mirroring login_lock:email:* on
            # the login flow (see login_protection_service's other caller).
            # Without this, the IP-keyed lock_key above is the only backstop:
            # a leaked/stolen refresh token replayed from many different IPs
            # (a botnet, rotating proxies, a mobile connection that changes
            # IP) never accumulates enough failures on any single IP key to
            # lock out, while two unrelated accounts sharing one IP (same
            # office network/NAT) can lock each other out of refresh through
            # no fault of their own. decode_payload does signature+expiry
            # checks only, deliberately skipping the revocation check (same
            # reason jwt_service.decode_payload exists for reuse-detection
            # below this handler's own call chain) - a stolen-but-still-
            # correctly-signed token still yields its account email even
            # once revoked/stale, which is exactly the token this dimension
            # needs to catch. A token that fails signature verification
            # entirely (a guess, not a leaked real token) yields no email;
            # the IP-keyed lock above already covers that case.
            account_lock_key: str | None = None
            payload = await jwt_service.decode_payload(refresh_token)
            email = payload.get("email") if payload else None
            if email:
                account_lock_key = f"refresh:lockout:account:{email}"

            allowed = await rate_limiter_service.record_request(rate_key)
            if not allowed:
                raise AppError(
                    status_code=429,
                    code="TOO_MANY_REFRESH_ATTEMPTS",
                    detail="Too many refresh attempts. Try again later."
                )

            is_locked = await login_protection_service.is_locked(lock_key)
            if not is_locked and account_lock_key:
                is_locked = await login_protection_service.is_locked(account_lock_key)
            if is_locked:
                raise AppError(
                    status_code=429,
                    code="TOO_MANY_FAILED_REFRESH_ATTEMPTS",
                    detail="Too many failed refresh attempts. Try later."
                )

            # refresh_tokens returns a plain dict[str, str], not the schema;
            # convert it the same way oauth2_login_handler does, rather than
            # accessing attributes that a dict doesn't have.
            tokens_dict = await refresh_token_service.refresh_tokens(refresh_token, db, request)

            if not tokens_dict or not tokens_dict.get("access_token"):
                await login_protection_service.record_failed_attempt(lock_key)
                if account_lock_key:
                    await login_protection_service.record_failed_attempt(account_lock_key)
                raise AppError(
                    status_code=401,
                    code="INVALID_OR_REVOKED_REFRESH_TOKEN",
                    detail="Invalid or revoked refresh token"
                )

            tokens = TokenPairResponseSchema(**tokens_dict)

            await login_protection_service.reset_failed_attempts(lock_key)
            if account_lock_key:
                await login_protection_service.reset_failed_attempts(account_lock_key)

            response = JSONResponse(content={"message": "Tokens refreshed successfully"})

            token_cookie_handler.set_tokens_in_cookies(response, tokens)

            return response

        except HTTPException:
            raise

        except Exception as exc:
            logger.error("Error in refresh token handler:\n%s", traceback.format_exc())
            raise AppError(status_code=500, code="INTERNAL_SERVER_ERROR", detail="Internal Server Error") from exc


refresh_token_handler = RefreshTokenHandler()
