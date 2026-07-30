import traceback

from ...logging.logging_config import get_logger
from ...user_crud.user_crud_collector import user_crud

logger = get_logger(__name__)


class UserVerificationService:
    """Marks a user as verified in the users table."""

    @staticmethod
    async def mark_user_verified(email: str, db) -> bool:
        try:
            user = await user_crud.get_by_email(email, db)

            if not user:
                logger.warning("Verification attempted for non-existent user: %s", email)
                return False

            if user.is_verified:
                logger.info("User %s is already verified", email)
                return False

            await user_crud.update_by_email(email, {"is_verified": True}, db)

            logger.info("User %s successfully marked as verified", email)

            return True

        except Exception:
            logger.error("Error marking user verified:\n%s", traceback.format_exc())
            return False


user_verification_service = UserVerificationService()
