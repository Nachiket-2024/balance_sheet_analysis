import traceback

from fastapi import Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ...audit_log.audit_log_service import PASSWORD_RESET_REQUESTED, log_security_event
from ...logging.logging_config import get_logger
from ..password_logic.password_reset_service import password_reset_service

logger = get_logger(__name__)


class PasswordResetRequestHandler:
    """Processes password reset requests, sending a reset email if the user exists."""

    def __init__(self):
        self.password_reset_service = password_reset_service

    async def handle_password_reset_request(
        self, email: str, db: AsyncSession | None = None, request: Request | None = None
    ) -> JSONResponse:
        try:
            # Service internally checks if user exists; returns False if not found.
            email_sent = await self.password_reset_service.send_reset_email(email, db)

            if not email_sent:
                logger.info("Password reset requested for non-existing email: %s", email)
                # user_email intentionally omitted (unattributed row, see
                # audit_log_model's support for user_email=NULL): recording
                # which specific address was probed would defeat the same
                # anti-enumeration reasoning this endpoint's response already
                # protects, but the probe itself must still show up in the
                # Security Log, otherwise this flow is invisible to review.
                await log_security_event(PASSWORD_RESET_REQUESTED, db, success=False, request=request)
            else:
                # Only audit-log a real request, matching signup_handler's
                # anti-enumeration reasoning (never persist a signal that would
                # let an attacker distinguish "no such account" from "request
                # sent" via a side channel).
                await log_security_event(
                    PASSWORD_RESET_REQUESTED, db, user_email=email, success=True, request=request
                )

            # Always return 200 regardless of whether the user exists: prevents
            # email enumeration.
            return JSONResponse(
                content={"message": "If the email exists, a reset link has been sent."},
                status_code=200
            )

        except Exception:
            logger.error("Error during password reset request logic:\n%s", traceback.format_exc())
            return JSONResponse(
                content={"error": "Internal Server Error", "code": "INTERNAL_SERVER_ERROR"}, status_code=500
            )


password_reset_request_handler = PasswordResetRequestHandler()
