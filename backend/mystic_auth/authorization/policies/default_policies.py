# Names of the three policies this template seeds out of the box. The actual
# policy definitions (actions, resource_type, conditions) live only in the
# Alembic migration that creates and seeds the policies/user_policies tables:
# migrations are a historical record and must keep producing the same rows
# regardless of later edits to application-code constants, so the migration
# deliberately keeps its own inline copy rather than importing from here.
#
# These name constants are the reusable part, used to look up and assign the
# already-seeded policies by name.
#   - signup_service assigns SELF_SERVICE_POLICY_NAME to every new user.
#   - scripts/create_system_user.py assigns all three to the system superuser.
#
# Action identifiers (defined in the migration, not here) match
# authorization/permissions.py's Permission enum values. That enum remains the
# action vocabulary; only the old role-permission mapping was RBAC and has been
# removed.

from ...core.settings import settings
from ...logging.logging_config import get_logger
from ..repositories.policy_repository import policy_repository

SELF_SERVICE_POLICY_NAME = "self_service"
USER_ADMINISTRATION_POLICY_NAME = "user_administration"
SYSTEM_SUPERUSER_POLICY_NAME = "system_superuser"

logger = get_logger(__name__)


async def assign_app_default_policies(user_id: int, db, assigned_by: str = "system") -> None:
    """Assigns every policy named in settings.DEFAULT_APP_POLICIES to a user.

    The extension point downstream apps use to get their own default policy
    set onto every account without editing signup_service.py / oauth2_service.py
    / user_verification_service.py: set DEFAULT_APP_POLICIES in .env, nothing
    else changes. Empty (default) is a no-op.

    Only call this once a user is already known to be verified. self_service
    is granted separately, at signup, regardless of verification state.
    """
    for policy_name in settings.default_app_policy_names:
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
