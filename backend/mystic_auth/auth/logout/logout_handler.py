import traceback

from fastapi import Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ...audit_log.audit_log_service import LOGOUT, log_security_event
from ...logging.logging_config import get_logger
from ..refresh_token_logic.refresh_token_service import refresh_token_service

logger = get_logger(__name__)


class LogoutHandler:
    """Revokes the refresh token, clears auth cookies, and returns the logout response."""

    def __init__(self):
        self.refresh_token_service = refresh_token_service

    async def handle_logout(
        self, refresh_token: str | None, db: AsyncSession | None = None, request: Request | None = None
    ) -> JSONResponse:
        try:
            if not refresh_token:
                return JSONResponse(
                    content={"error": "No refresh token cookie found"},
                    status_code=400
                )

            success = await self.refresh_token_service.revoke_refresh_token(refresh_token)

            await log_security_event(LOGOUT, db, success=success, request=request)

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

            resp.delete_cookie(key="access_token", httponly=True, secure=True, samesite="strict")

            # path must match the path="/auth" it was set with
            # (token_cookie_handler.py), or the browser treats this as a different
            # cookie and never clears it.
            resp.delete_cookie(key="refresh_token", httponly=True, secure=True, samesite="strict", path="/auth")

            return resp

        except Exception:
            logger.error("Error during logout logic:\n%s", traceback.format_exc())
            return JSONResponse(
                content={"error": "Internal Server Error"},
                status_code=500
            )


logout_handler = LogoutHandler()
