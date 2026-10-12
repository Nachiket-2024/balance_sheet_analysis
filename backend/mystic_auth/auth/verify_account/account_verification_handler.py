import traceback

from fastapi import Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ...audit_log.audit_log_service import ACCOUNT_VERIFICATION_REQUESTED, ACCOUNT_VERIFIED, log_security_event
from ...logging.logging_config import get_logger
from ..security.login_protection_service import login_protection_service
from .account_verification_service import account_verification_service
from .user_verification_service import user_verification_service

logger = get_logger(__name__)


class AccountVerificationHandler:
    """Verifies an account via email token and enforces login protection."""

    def __init__(self):
        self.account_verification_service = account_verification_service
        self.user_verification_service = user_verification_service
        self.login_protection_service = login_protection_service

    async def handle_account_verification(
        self, token: str, db: AsyncSession, request: Request | None = None
    ) -> JSONResponse:
        try:
            # Inspect the signed token first; redemption happens only after
            # the atomic action reservation succeeds, so a locked caller
            # cannot burn a valid one-time verification link.
            payload = await self.account_verification_service.verify_token(token, consume=False)

            if not payload or "email" not in payload:
                return JSONResponse(
                    content={
                        "error": "Invalid, expired, or already used verification token",
                        "code": "INVALID_VERIFICATION_TOKEN",
                    },
                    status_code=400
                )

            email = payload["email"]

            # Distinct namespace from login's "login_lock:email:" key: sharing
            # it would mean a burst of failed verification attempts (e.g. a
            # double-submitted, already-consumed link) counts towards, and can
            # trip, the unrelated login lockout for the same email. Same
            # reasoning as refresh_token_handler's separate "refresh:lockout:ip:" key.
            email_lock_key = f"verify_account_lock:email:{email}"

            # Enforce the lock before changing account state. A successful
            # verification must not be reported as 429 after the account has
            # already been marked verified.
            if not await self.login_protection_service.begin_protected_action(email_lock_key):
                return JSONResponse(
                    content={
                        "error": "Too many failed attempts, account temporarily locked",
                        "code": "ACCOUNT_LOCKED",
                    },
                    status_code=429,
                )

            if not await self.account_verification_service.consume_token(token):
                await self.login_protection_service.release_protected_action(email_lock_key)
                return JSONResponse(
                    content={
                        "error": "Invalid, expired, or already used verification token",
                        "code": "INVALID_VERIFICATION_TOKEN",
                    },
                    status_code=400,
                )

            try:
                updated = await self.user_verification_service.mark_user_verified(email, db)

                await log_security_event(
                    ACCOUNT_VERIFIED, db, user_email=email, success=updated, request=request
                )

                if updated:
                    content = {"message": f"Account verified successfully for {email}."}
                    await self.login_protection_service.finish_protected_action(email_lock_key, success=True)
                    return JSONResponse(content, status_code=200)

                content = {"error": "User not found or already verified", "code": "USER_NOT_FOUND_OR_ALREADY_VERIFIED"}
                await self.login_protection_service.finish_protected_action(email_lock_key, success=False)
                if await self.login_protection_service.is_locked(email_lock_key):
                    return JSONResponse(
                        content={
                            "error": "Too many failed attempts, account temporarily locked",
                            "code": "ACCOUNT_LOCKED",
                        },
                        status_code=429,
                    )
                return JSONResponse(content, status_code=400)
            finally:
                await self.login_protection_service.release_protected_action(email_lock_key)

        except Exception:
            logger.error("Error during account verification:\n%s", traceback.format_exc())
            return JSONResponse(
                content={"error": "Internal Server Error", "code": "INTERNAL_SERVER_ERROR"}, status_code=500
            )

    async def handle_verification_email_request(
        self, email: str, db: AsyncSession, request: Request | None = None
    ) -> JSONResponse:
        try:
            email_sent = await self.account_verification_service.send_verification_email_if_needed(email, db)

            await log_security_event(
                ACCOUNT_VERIFICATION_REQUESTED,
                db,
                # Do not retain an arbitrary unknown email from an
                # enumeration-resistant request. Known successful delivery
                # requests retain the account identity for investigation.
                user_email=email if email_sent else None,
                success=email_sent,
                request=request,
                metadata={"delivery_queued": email_sent},
            )

            return JSONResponse(
                content={
                    "message": "If this account exists and still needs verification, we've sent a new verification link."
                },
                status_code=200,
            )

        except Exception:
            logger.error("Error during verification email request:\n%s", traceback.format_exc())
            return JSONResponse(
                content={"error": "Internal Server Error", "code": "INTERNAL_SERVER_ERROR"}, status_code=500
            )


account_verification_handler = AccountVerificationHandler()
