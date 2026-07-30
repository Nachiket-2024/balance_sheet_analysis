import traceback

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ...auth.refresh_token_logic.refresh_token_service import refresh_token_service
from ...auth.security.login_protection_service import login_protection_service
from ...auth.security.rate_limiter_service import rate_limiter_service
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
    async def handle_refresh_tokens(request: Request, refresh_token: str | None, db: AsyncSession | None = None):
        try:
            # Same 401 outcome as an invalid token, so a client can't distinguish
            # "never had a session" from "had one that's now invalid" purely from
            # this response.
            if not refresh_token:
                raise HTTPException(
                    status_code=401,
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

            allowed = await rate_limiter_service.record_request(rate_key)
            if not allowed:
                raise HTTPException(
                    status_code=429,
                    detail="Too many refresh attempts. Try again later."
                )

            is_locked = await login_protection_service.is_locked(lock_key)
            if is_locked:
                raise HTTPException(
                    status_code=429,
                    detail="Too many failed refresh attempts. Try later."
                )

            # refresh_tokens returns a plain dict[str, str], not the schema;
            # convert it the same way oauth2_login_handler does, rather than
            # accessing attributes that a dict doesn't have.
            tokens_dict = await refresh_token_service.refresh_tokens(refresh_token, db, request)

            if not tokens_dict or not tokens_dict.get("access_token"):
                await login_protection_service.record_failed_attempt(lock_key)
                raise HTTPException(
                    status_code=401,
                    detail="Invalid or revoked refresh token"
                )

            tokens = TokenPairResponseSchema(**tokens_dict)

            await login_protection_service.reset_failed_attempts(lock_key)

            response = JSONResponse(content={"message": "Tokens refreshed successfully"})

            token_cookie_handler.set_tokens_in_cookies(response, tokens)

            return response

        except HTTPException:
            raise

        except Exception as exc:
            logger.error("Error in refresh token handler:\n%s", traceback.format_exc())
            raise HTTPException(status_code=500, detail="Internal Server Error") from exc


refresh_token_handler = RefreshTokenHandler()
