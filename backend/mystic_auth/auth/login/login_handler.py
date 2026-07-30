import asyncio
import traceback

from fastapi import Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ...audit_log.audit_log_service import ACCOUNT_LOCKED, LOGIN_FAILURE, LOGIN_SUCCESS, log_security_event
from ...logging.logging_config import get_logger
from ..security.login_protection_service import login_protection_service
from ..token_logic.token_cookie_handler import token_cookie_handler
from ..token_logic.token_schema import TokenPairResponseSchema
from .login_service import login_service

logger = get_logger(__name__)


class LoginHandler:
    """Validates input, authenticates the user, applies login protection, and sets JWT cookies."""

    @staticmethod
    def _lockout_response() -> JSONResponse:
        # Both the pre-auth pre-check and the post-auth recheck can deny a login for
        # the same reason; defined once so the two call sites can't drift.
        return JSONResponse(
            content={
                "error": "Too many failed login attempts, account temporarily locked"
            },
            status_code=429,
        )

    async def handle_login(
        self,
        email: str,
        password: str,
        client_ip: str = "unknown",
        db: AsyncSession | None = None,
        request: Request | None = None,
    ):
        """
        client_ip keys an additional lockout counter alongside the email-based one.
        This counter aggregates failed attempts across ANY account from a single IP:
        the email-keyed counter alone never trips for an attacker credential-stuffing/
        spraying many different emails from one source, since no single email ever
        crosses its own threshold.
        """
        try:
            if not email or not password:
                return JSONResponse(
                    content={"error": "Email and password are required"},
                    status_code=400,
                )

            email_lock_key = f"login_lock:email:{email}"
            ip_lock_key = f"login_lock:ip:{client_ip}"

            # Reject immediately if either the account or the source IP is already
            # locked out, before spending effort on a DB lookup and password hash
            # comparison. Still logged, so repeated attempts against an
            # already-locked target keep showing up in the audit trail instead of
            # only the single attempt that originally crossed the threshold.
            if await login_protection_service.is_locked(email_lock_key):
                await log_security_event(
                    ACCOUNT_LOCKED, db, user_email=email, success=False, request=request
                )
                return self._lockout_response()

            if await login_protection_service.is_locked(
                ip_lock_key, max_attempts=login_protection_service.MAX_FAILED_LOGIN_ATTEMPTS_PER_IP
            ):
                await log_security_event(
                    ACCOUNT_LOCKED, db, user_email=email, success=False, request=request
                )
                return self._lockout_response()

            tokens: TokenPairResponseSchema | None = await login_service.login(
                email=email, password=password, db=db
            )

            success = tokens is not None

            # Audit entry for the credential-check outcome, independent of any
            # lockout state applied afterwards.
            await log_security_event(
                LOGIN_SUCCESS if success else LOGIN_FAILURE,
                db,
                user_email=email,
                success=success,
                request=request,
            )

            # Record the real outcome against both counters so failed attempts count
            # towards each threshold independently and successful ones reset each.
            # The two counters are independent Redis keys, so record them concurrently.
            email_allowed, ip_allowed = await asyncio.gather(
                login_protection_service.check_and_record_action(
                    email_lock_key, success=success
                ),
                login_protection_service.check_and_record_action(
                    ip_lock_key,
                    success=success,
                    max_attempts=login_protection_service.MAX_FAILED_LOGIN_ATTEMPTS_PER_IP,
                    lockout_time=login_protection_service.LOGIN_LOCKOUT_TIME_PER_IP,
                ),
            )

            if not email_allowed or not ip_allowed:
                await log_security_event(
                    ACCOUNT_LOCKED, db, user_email=email, success=False, request=request
                )
                return self._lockout_response()

            if not tokens:
                return JSONResponse(
                    content={"error": "Invalid credentials or account locked"},
                    status_code=401,
                )

            response = JSONResponse(content={"message": "Login successful"})
            return token_cookie_handler.set_tokens_in_cookies(response, tokens)

        except Exception:
            logger.error("Error during login:\n%s", traceback.format_exc())
            return JSONResponse(
                content={"error": "Internal Server Error"}, status_code=500
            )


login_handler = LoginHandler()
