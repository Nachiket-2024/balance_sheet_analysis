import asyncio
import traceback
from datetime import UTC, datetime, timedelta

import jwt
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.token_logic.jwt_service import jwt_service
from ..core.settings import settings
from ..emails.email_template_service import render_transactional_email
from ..logging.logging_config import get_logger
from ..procrastinate_tasks.email_tasks import send_email_task
from ..user.user_crud_collector import user_crud
from ..valkey.client import valkey_client
from .user_self_deletion_service import finalize_self_deletion

logger = get_logger(__name__)


class AccountDeletionService:
    """
    Async, email-confirmed self-service account-deletion flow for
    OAuth-only accounts (hashed_password is None, so there's no password to
    re-confirm with synchronously; see
    user_self_service_routes.py::delete_my_account for the password-holding
    account's synchronous path). Modeled on
    auth/password_logic/password_reset_service.py: a signed, single-use JWT
    emailed as a link, redeemed exactly once via Valkey GETDEL.
    """

    @staticmethod
    async def create_account_deletion_token(
        email: str,
        expires_minutes: int = settings.ACCOUNT_DELETE_TOKEN_EXPIRE_MINUTES,
    ) -> str:
        expire = datetime.now(UTC) + timedelta(minutes=expires_minutes)

        # The "account_delete" type claim rejects any other validly-signed
        # JWT (access, refresh, reset) carrying an "email" claim, so tokens
        # can't be swapped between these otherwise-similar flows.
        payload: dict[str, str | float] = {
            "email": email,
            "type": "account_delete",
            "exp": expire.timestamp(),
            "iss": settings.JWT_ISSUER,
            "aud": settings.JWT_AUDIENCE,
        }

        # Off the event loop, same as password_service.create_reset_token:
        # PyJWT's encode is sync.
        return await asyncio.to_thread(jwt.encode, payload, settings.SECRET_KEY, settings.JWT_ALGORITHM)

    @staticmethod
    async def verify_account_deletion_token(token: str) -> dict | None:
        try:
            # verify_aud disabled: PyJWT rejects any "aud" claim outright,
            # which would break tokens minted before that claim existed.
            # has_valid_issuer_and_audience below does the real check:
            # absent is fine, present-and-wrong is not.
            payload = await asyncio.to_thread(
                jwt.decode,
                token,
                settings.SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM],
                options={"verify_aud": False},
            )

            if not payload.get("email"):
                return None

            if payload.get("type") != "account_delete":
                return None

            if not jwt_service.has_valid_issuer_and_audience(payload):
                return None

            return payload

        except jwt.ExpiredSignatureError:
            return None

        except jwt.InvalidTokenError:
            return None

    @staticmethod
    async def send_deletion_email(user, db: AsyncSession) -> bool:
        try:
            email = user.email
            token = await account_deletion_service.create_account_deletion_token(email)

            expires_minutes = settings.ACCOUNT_DELETE_TOKEN_EXPIRE_MINUTES

            # Persisted in Valkey so confirm_deletion() can enforce single
            # use; without it the JWT stays valid and replayable for the
            # whole expiry window even after being redeemed once.
            await valkey_client.set(f"account_delete:{token}", "1", ex=expires_minutes * 60)

            # Fragments stay in the browser and are not sent in HTTP requests
            # or Referer headers.
            deletion_url = f"{settings.FRONTEND_BASE_URL}/confirm-delete#token={token}"

            email_subject = "Confirm Account Deletion"
            email_body = render_transactional_email(
                preheader="Confirm you want to permanently delete your account.",
                heading="Confirm Account Deletion",
                # Red, unlike the reset/verification emails' brand color:
                # this deactivates the account immediately, so a more
                # consequential-looking CTA fits.
                accent_color="#c53030",
                intro=(
                    "A deletion request was made for your account. Click the button below to "
                    "confirm - your account will be deactivated immediately and signed out "
                    "everywhere, then permanently removed after the standard "
                    f"{settings.ACCOUNT_PURGE_GRACE_DAYS}-day recovery window."
                ),
                cta_label="Confirm Account Deletion",
                cta_url=deletion_url,
                expiry_note=f"This confirmation link will expire in {expires_minutes} minutes for security reasons.",
                ignore_note="If you didn't request this, you can safely ignore this email; your account will remain unchanged.",
            )

            await send_email_task.defer_async(
                to_email=email,
                subject=email_subject,
                body=email_body,
                is_html=True,
            )

            logger.info("Account deletion confirmation email scheduled for %s", email)
            return True

        except Exception:
            logger.error("Error sending account deletion confirmation email:\n%s", traceback.format_exc())
            return False

    @staticmethod
    async def confirm_deletion(token: str, db: AsyncSession, request: Request | None = None) -> bool:
        """
        Atomically fetch-and-delete the Valkey entry (GETDEL, not GET+DEL) so
        reuse/replay is impossible: two concurrent requests with the same
        valid link could otherwise both pass a plain GET before either
        deleted the key, and both then run the deletion. Same race, same
        fix, as password_reset_service.reset_password. Unlike that flow
        there's no recoverable-validation-failure case worth restoring the
        token for (no equivalent to "weak new password"): once the token
        verifies and the Valkey entry is redeemed, the only remaining failure
        is "user not found", which a retry can't fix either.
        """
        try:
            payload = await account_deletion_service.verify_account_deletion_token(token)
            if not payload:
                logger.warning("Invalid or expired account deletion token")
                return False

            if not await valkey_client.getdel(f"account_delete:{token}"):
                logger.warning("Account deletion token not found or already used")
                return False

            email = payload.get("email")
            if not email:
                logger.warning("Email missing from account deletion token payload")
                return False

            user = await user_crud.get_by_email(email, db)
            if not user:
                logger.warning("User not found during account deletion confirm for email: %s", email)
                return False

            await finalize_self_deletion(user, db, request=request)

            logger.info("Account deletion confirmed for email: %s", email)
            return True

        except Exception:
            logger.error("Error during account deletion confirm:\n%s", traceback.format_exc())
            return False


account_deletion_service = AccountDeletionService()
