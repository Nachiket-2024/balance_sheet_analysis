import traceback

from fastapi import Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ...audit_log.audit_log_service import SIGNUP, log_security_event
from ...logging.logging_config import get_logger
from ..password_logic.password_service import password_service
from ..verify_account.account_verification_service import account_verification_service
from .signup_service import signup_service

logger = get_logger(__name__)


class SignupHandler:
    """Handles user signup: validation, account creation, and verification email dispatch."""

    @staticmethod
    async def handle_signup(
        name: str, email: str, password: str, db: AsyncSession | None = None, request: Request | None = None
    ):
        """
        Always returns the same generic response regardless of whether the
        account already existed. Returning a different status code or message
        for "email already registered" would let an attacker enumerate which
        emails have accounts on this site, the same reason
        password_reset_request_handler always returns a generic message too.
        """
        try:
            if not name or not email or not password:
                return JSONResponse(
                    content={
                        "error": "Name, email, and password are required",
                        "code": "NAME_EMAIL_PASSWORD_REQUIRED",
                    },
                    status_code=400
                )

            # Runs regardless of whether the email is already registered, so it
            # carries no enumeration signal: unlike the "email already
            # registered" case, telling a user their own chosen password is weak
            # doesn't reveal anything about other accounts.
            if not await password_service.validate_password_strength(password):
                return JSONResponse(
                    content={
                        "error": "Password does not meet minimum strength requirements",
                        "code": "PASSWORD_TOO_WEAK",
                    },
                    status_code=400
                )

            # Role is hardcoded to UserRole.user inside signup_service, not passed here.
            user_created = await signup_service.signup(
                name=name,
                email=email,
                password=password,
                db=db
            )

            # Only send a verification email for a genuinely new account, never
            # for an email that's already registered, so repeated signup
            # attempts can't be used to spam an existing user's inbox.
            if user_created:
                await account_verification_service.send_verification_email(email)
                await log_security_event(SIGNUP, db, user_email=email, success=True, request=request)

            return JSONResponse(
                content={
                    "message": "If this email is not already registered, we've sent a verification link to it."
                },
                status_code=200
            )

        except Exception:
            logger.error("Error during signup logic:\n%s", traceback.format_exc())
            return JSONResponse(
                content={"error": "Internal Server Error", "code": "INTERNAL_SERVER_ERROR"},
                status_code=500
            )


signup_handler = SignupHandler()
