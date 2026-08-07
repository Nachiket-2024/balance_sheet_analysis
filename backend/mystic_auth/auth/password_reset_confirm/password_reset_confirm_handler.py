import traceback

from fastapi import Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ...audit_log.audit_log_service import PASSWORD_RESET_CONFIRMED, log_security_event
from ...logging.logging_config import get_logger
from ..password_logic.password_reset_service import password_reset_service
from ..password_logic.password_service import password_service
from ..security.login_protection_service import login_protection_service

logger = get_logger(__name__)


class PasswordResetConfirmHandler:
    """Verifies a reset token, resets the password, and enforces login protection."""

    def __init__(self):
        self.password_service = password_service
        self.password_reset_service = password_reset_service
        self.login_protection_service = login_protection_service

    async def handle_password_reset_confirm(
        self, token: str, new_password: str, db: AsyncSession | None = None, request: Request | None = None
    ) -> JSONResponse:
        try:
            # Must scope to type=="reset" here, not a generic verify_token: any
            # validly-signed JWT with an "email" claim (an access/refresh/verify
            # token) would otherwise pass, letting an attacker holding one for a
            # victim account poison their audit log and trip their reset lockout.
            payload = await self.password_service.verify_reset_token(token)

            if not payload or "email" not in payload:
                return JSONResponse({"error": "Invalid or expired token"}, status_code=400)

            email = payload["email"]

            # Distinct namespace from login's "login_lock:email:" key: sharing it
            # would mean failures unrelated to a real login attempt (a weak new
            # password, reusing the old password, a stale token) count towards,
            # and can trip, the unrelated login lockout for the same email. Same
            # reasoning as refresh_token_handler's separate "refresh:lockout:ip:" key.
            email_lock_key = f"password_reset_confirm_lock:email:{email}"

            success = await self.password_reset_service.reset_password(token, new_password, db)

            await log_security_event(
                PASSWORD_RESET_CONFIRMED, db, user_email=email, success=success, request=request
            )

            status = 200 if success else 400
            content = {"message": "Password has been reset successfully"} if success else {"error": "Invalid token or password"}

            allowed = await self.login_protection_service.check_and_record_action(
                email_lock_key, success=(status == 200)
            )

            if not allowed:
                return JSONResponse({"error": "Too many failed attempts, temporarily locked"}, status_code=429)

            return JSONResponse(content, status_code=status)

        except Exception:
            logger.error("Error during password reset confirm logic:\n%s", traceback.format_exc())
            return JSONResponse({"error": "Internal Server Error"}, status_code=500)


password_reset_confirm_handler = PasswordResetConfirmHandler()
