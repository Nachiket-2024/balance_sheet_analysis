import traceback

from fastapi import Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ...audit_log.audit_log_service import LOGOUT_ALL, log_security_event
from ...logging.logging_config import get_logger
from ..refresh_token_logic.refresh_token_service import refresh_token_service
from ..token_logic.jwt_service import jwt_service

logger = get_logger(__name__)


class LogoutAllHandler:
    """Revokes every session on the account (one account-wide Redis
    version bump - see refresh_token_service.revoke_all_tokens_for_user)
    and clears authentication cookies."""

    async def handle_logout_all(
        self, refresh_token: str | None, db: AsyncSession | None = None, request: Request | None = None
    ) -> JSONResponse:
        try:
            if not refresh_token:
                return JSONResponse(
                    content={"error": "No refresh token cookie found"},
                    status_code=400
                )

            # decode_payload, not verify_token: an already-revoked refresh
            # token (e.g. this device's own session, killed moments ago by a
            # password change that revokes every refresh token for the
            # account) must still resolve to its owning email so the rest of
            # that account's sessions can be revoked and cookies cleared,
            # instead of failing outright and leaving stale cookies behind.
            # decode_payload skips the revocation check verify_token does,
            # but NOT the "type" claim check: a wrong-type token (e.g. an
            # access token mistakenly presented here) must still be rejected
            # for revocation purposes, same as refresh_tokens() in
            # refresh_token_service.py.
            payload = await jwt_service.decode_payload(refresh_token)

            email = payload.get("email") if payload and payload.get("type") == "refresh" else None

            revoked_count = await refresh_token_service.revoke_all_tokens_for_user(email, db) if email else 0

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
            resp.delete_cookie(key="access_token", httponly=True, secure=True, samesite="none")
            # path must match the path="/auth" refresh_token was set with
            # (token_cookie_handler.py), or the browser treats this as a different
            # cookie and never clears the real one.
            resp.delete_cookie(key="refresh_token", httponly=True, secure=True, samesite="none", path="/auth")

            return resp

        except Exception:
            logger.error("Error during logout-all logic:\n%s", traceback.format_exc())
            return JSONResponse(content={"error": "Internal Server Error"}, status_code=500)


logout_all_handler = LogoutAllHandler()
