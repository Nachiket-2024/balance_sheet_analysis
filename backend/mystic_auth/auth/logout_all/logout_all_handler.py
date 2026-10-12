import traceback

from fastapi import Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ...audit_log.audit_log_service import LOGOUT_ALL, log_security_event
from ...logging.logging_config import get_logger
from ..refresh_token_logic.refresh_token_service import refresh_token_service
from ..token_logic.jwt_service import jwt_service
from ..token_logic.token_cookie_handler import token_cookie_handler
from ..token_logic.token_version_store import TokenVersionUnavailableError

logger = get_logger(__name__)


class LogoutAllHandler:
    """Revokes every session on the account (one account-wide Valkey
    version bump - see refresh_token_service.revoke_all_tokens_for_user)
    and clears authentication cookies."""

    async def handle_logout_all(
        self, refresh_token: str | None, db: AsyncSession | None = None, request: Request | None = None
    ) -> JSONResponse:
        try:
            if not refresh_token:
                return JSONResponse(
                    content={"error": "No refresh token cookie found", "code": "NO_REFRESH_TOKEN_COOKIE"},
                    status_code=400
                )

            # decode_payload, not verify_token: an already-revoked refresh token
            # must still resolve to its owning email so the rest of that
            # account's sessions can be revoked and cookies cleared, rather than
            # failing outright and leaving stale cookies behind. It still enforces
            # the "type" claim, though, so a wrong-type token is still rejected
            # (same as refresh_tokens() in refresh_token_service.py).
            payload = await jwt_service.decode_payload(refresh_token)

            email = payload.get("email") if payload and payload.get("type") == "refresh" else None

            try:
                revoked_count = await refresh_token_service.revoke_all_tokens_for_user(email, db) if email else 0
            except TokenVersionUnavailableError:
                # Unlike plain logout, revoking every session IS this
                # request's entire purpose - reporting success here would be
                # a false "done" while every existing token on the account
                # stays valid. Cookies are still cleared (this browser's own
                # goal is met regardless), but the response must not look
                # like a completed logout-all.
                await log_security_event(
                    LOGOUT_ALL, db, user_email=email, success=False, request=request,
                    metadata={"error": "valkey_unavailable"},
                )
                resp = JSONResponse(
                    content={
                        "error": "Could not confirm logout from all devices; please try again shortly",
                        "code": "SESSION_REVOCATION_UNAVAILABLE",
                    },
                    status_code=503,
                )
                token_cookie_handler.clear_tokens_from_cookies(resp)
                return resp

            await log_security_event(
                LOGOUT_ALL,
                db,
                user_email=email,
                success=revoked_count > 0,
                request=request,
                metadata={"revoked_count": revoked_count},
            )

            # As with plain logout: whether or not there was anything left to
            # revoke server-side, the caller's goal (no valid session left
            # in this browser) is met either way, so this always clears
            # cookies and reports success rather than erroring out.
            resp = JSONResponse(
                content={"message": f"Logged out from {revoked_count} devices"},
                status_code=200
            )
            token_cookie_handler.clear_tokens_from_cookies(resp)

            return resp

        except Exception:
            logger.error("Error during logout-all logic:\n%s", traceback.format_exc())
            return JSONResponse(
                content={"error": "Internal Server Error", "code": "INTERNAL_SERVER_ERROR"}, status_code=500
            )


logout_all_handler = LogoutAllHandler()
