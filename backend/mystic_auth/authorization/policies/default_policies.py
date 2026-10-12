# Names of the three seeded policies. Definitions live only in the Alembic
# migration (must keep producing the same rows regardless of later constant
# edits); these names are used to look up and assign them elsewhere.

from ...logging.logging_config import get_logger
from ..repositories.policy_repository import policy_repository

try:
    from backend.app.core.settings import app_settings
except ModuleNotFoundError:
    from app.core.settings import app_settings

SELF_SERVICE_POLICY_NAME = "self_service"
USER_MANAGEMENT_POLICY_NAME = "user_management"
SYSTEM_SUPERUSER_POLICY_NAME = "system_superuser"

logger = get_logger(__name__)


async def assign_app_default_policies(user_id: int, db, assigned_by: str = "system") -> None:
    """Assigns every policy named in app_settings.DEFAULT_APP_POLICIES to a user.

    Extension point for downstream apps to get their own default policy set
    without editing signup/oauth2/verification services: set the app-owned
    DEFAULT_APP_POLICIES in env/app/.env.<mode>. Empty (default) is a no-op.

    Only call once a user is verified. self_service is granted separately,
    at signup, regardless of verification state.
    """
    for policy_name in app_settings.default_app_policy_names:
        policy = await policy_repository.get_by_name(policy_name, db)
        if policy:
            await policy_repository.assign_policy_to_user(
                user_id=user_id, policy_id=policy.id, db=db, assigned_by=assigned_by
            )
        else:
            # Misconfiguration, not this request's fault: log, don't raise.
            logger.error(
                "Configured default app policy '%s' (DEFAULT_APP_POLICIES) not found; "
                "skipping assignment for user_id=%s", policy_name, user_id,
            )
