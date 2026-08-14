import traceback

from fastapi import Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ...audit_log.audit_log_service import LOGOUT, log_security_event
from ...logging.logging_config import get_logger
from ...user_session.session_service import session_service
from ..token_logic.jwt_service import jwt_service

logger = get_logger(__name__)


class LogoutHandler:
    """Ends exactly the caller's own current session (bumps its chain's
    Redis version - see session_service.revoke_session_on_logout), clears
    auth cookies, and returns the logout response."""

    async def handle_logout(
        self, refresh_token: str | None, db: AsyncSession | None = None, request: Request | None = None
    ) -> JSONResponse:
        try:
            if not refresh_token:
                return JSONResponse(
                    content={"error": "No refresh token cookie found", "code": "NO_REFRESH_TOKEN_COOKIE"},
                    status_code=400
                )

            # decode_payload, not verify_token: an already-revoked/expired
            # refresh token must still resolve to its owning email so the
            # audit trail records who logged out, instead of silently
            # falling back to None (see logout_all_handler.py's identical
            # reasoning for why decode_payload specifically).
            payload = await jwt_service.decode_payload(refresh_token)
            email = payload.get("email") if payload and payload.get("type") == "refresh" else None
            jti = payload.get("jti") if payload and payload.get("type") == "refresh" else None

            await session_service.revoke_session_on_logout(db, jti, email)

            await log_security_event(LOGOUT, db, user_email=email, success=bool(email), request=request)

            # Whether or not the presented refresh token was still live to
            # revoke (it may already be invalid/expired/revoked, e.g. this
            # device's session was killed by a password change moments ago,
            # which revokes every refresh token for the account), the
            # caller's actual goal, "no valid session left in this browser",
            # is met either way. Returning an error here instead of
            # clearing cookies used to leave the frontend stuck showing
            # "logged in" with a dead refresh-token cookie it could never
            # successfully log out of.
            resp = JSONResponse(
                content={"message": "Logged out successfully"},
                status_code=200
            )

            resp.delete_cookie(key="access_token", httponly=True, secure=True, samesite="none")

            # path must match the path="/auth" it was set with
            # (token_cookie_handler.py), or the browser treats this as a different
            # cookie and never clears it.
            resp.delete_cookie(key="refresh_token", httponly=True, secure=True, samesite="none", path="/auth")

            return resp

        except Exception:
            logger.error("Error during logout logic:\n%s", traceback.format_exc())
            return JSONResponse(
                content={"error": "Internal Server Error", "code": "INTERNAL_SERVER_ERROR"},
                status_code=500
            )


logout_handler = LogoutHandler()
