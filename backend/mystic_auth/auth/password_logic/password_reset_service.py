import traceback
from datetime import UTC, datetime

from ...core.settings import settings
from ...emails.email_template_service import render_transactional_email
from ...logging.logging_config import get_logger
from ...redis.client import redis_client
from ...taskiq_tasks.email_tasks import send_email_task
from ...user_crud.user_crud_collector import user_crud
from ..refresh_token_logic.refresh_token_service import refresh_token_service
from .password_service import password_service

logger = get_logger(__name__)


class PasswordResetService:
    """Handles password reset requests (email dispatch) and reset confirmation."""

    @staticmethod
    async def send_reset_email(email: str, db) -> bool:
        try:
            user = await user_crud.get_by_email(email, db)
            if not user:
                logger.warning("Password reset requested for non-existent email: %s", email)
                return False

            # Token carries only email; role is no longer needed for reset flow.
            reset_token = await password_service.create_reset_token(email)

            expires_minutes = settings.RESET_TOKEN_EXPIRE_MINUTES

            # Persisted in Redis so reset_password() can enforce single-use:
            # without this, a JWT's signature alone stays valid (and replayable)
            # for the whole expiry window even after being redeemed once.
            await redis_client.set(f"password_reset:{reset_token}", "1", ex=expires_minutes * 60)

            reset_url = f"{settings.FRONTEND_BASE_URL}/reset-password?token={reset_token}"

            email_subject = "Reset Your Password"
            email_body = render_transactional_email(
                preheader="Reset your password to regain access to your account.",
                heading="Reset Your Password",
                accent_color="#e53e3e",
                intro="A password reset was requested for your account. Click the button below to create a new password.",
                cta_label="Reset Your Password",
                cta_url=reset_url,
                expiry_note=f"This password reset link will expire in {expires_minutes} minutes for security reasons.",
                ignore_note="If you didn't request a password reset, you can safely ignore this email; your password will remain unchanged.",
            )

            await send_email_task.kiq(
                to_email=email,
                subject=email_subject,
                body=email_body,
                is_html=True
            )

            logger.info("Password reset email scheduled for %s", email)
            return True

        except Exception:
            logger.error("Error sending password reset email:\n%s", traceback.format_exc())
            return False

    @staticmethod
    async def reset_password(token: str, new_password: str, db) -> bool:
        """
        The single-use check used to be a plain GET, with the matching DELETE
        only issued after a successful password update, leaving a window where
        two concurrent requests carrying the same valid token could both pass
        the GET before either deleted the key. If they submitted different new
        passwords, both DB writes would execute and the later one would
        silently win, defeating the token's single-use guarantee. GETDEL makes
        "check unused" and "mark used" one atomic operation: only one
        concurrent request can ever win it, so at most one password update can
        happen per token. A request that wins the GETDEL but then fails a
        recoverable validation step (weak password, same-as-old password, a
        transient DB failure) restores the entry, with a TTL capped by the
        token's own remaining JWT lifetime, so a legitimate retry with the
        same link still works, without reopening the concurrency window this fixes.
        """
        redis_key = f"password_reset:{token}"

        async def _restore_token(payload: dict) -> None:
            # Cap the restored TTL at the token's own remaining JWT lifetime so
            # retries never extend the reset window past the original expiry;
            # verify_reset_token would reject the JWT by then anyway.
            exp = payload.get("exp")
            if not exp:
                return
            remaining = int(exp - datetime.now(UTC).timestamp())
            if remaining > 0:
                await redis_client.set(redis_key, "1", ex=remaining)

        try:
            payload = await password_service.verify_reset_token(token)
            if not payload:
                logger.warning("Invalid or expired password reset token")
                return False

            # Atomically fetch-and-delete so reuse/replay is impossible.
            if not await redis_client.getdel(redis_key):
                logger.warning("Password reset token not found or already used")
                return False

            # Role is no longer stored in reset tokens: single table makes it unnecessary.
            email = payload.get("email")
            if not email:
                logger.warning("Email missing from reset token payload")
                await _restore_token(payload)
                return False

            if not await password_service.validate_password_strength(new_password):
                logger.warning("Weak password provided during reset for email: %s", email)
                await _restore_token(payload)
                return False

            user = await user_crud.get_by_email(email, db)
            if not user:
                logger.warning("User not found during password reset for email: %s", email)
                await _restore_token(payload)
                return False

            if user.hashed_password:
                is_same_password = await password_service.verify_password(
                    new_password, user.hashed_password
                )
                if is_same_password:
                    logger.warning("Password reset attempted with same password for email: %s", email)
                    await _restore_token(payload)
                    return False

            hashed_password = await password_service.hash_password(new_password)

            updated = await user_crud.update_by_email(
                email, {"hashed_password": hashed_password}, db
            )

            if not updated:
                await _restore_token(payload)
                return False

            # A password reset is frequently done specifically because the
            # account may be compromised, so any session an attacker already
            # holds must not survive it.
            await refresh_token_service.revoke_all_tokens_for_user(email)

            logger.info("Password reset successful for email: %s", email)
            return True

        except Exception:
            logger.error("Error during password reset:\n%s", traceback.format_exc())
            return False


password_reset_service = PasswordResetService()
