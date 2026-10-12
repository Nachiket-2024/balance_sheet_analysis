import traceback

from sqlalchemy.exc import IntegrityError

from ...authorization.policies.default_policies import SELF_SERVICE_POLICY_NAME

# PBAC: new users get their access via an explicit default policy assignment,
# never via their (metadata-only) role: see the role-as-metadata invariant.
from ...authorization.repositories.policy_repository import policy_repository
from ...logging.logging_config import get_logger
from ...user.user_crud_collector import user_crud

# Default role assigned to all new users, metadata only (display/grouping); it
# grants no access. See the PBAC policy assignment below for what actually
# authorizes a new account.
from ...user.user_model import UserRole
from ..password_logic.password_service import password_service

logger = get_logger(__name__)


class SignupService:
    """Hashes the password, checks for duplicates, and creates the user with default access."""

    @staticmethod
    # `db` is deliberately unannotated: real callers pass an AsyncSession,
    # but unit tests call this with db=None while mocking the db-touching
    # collaborators, so neither `AsyncSession` nor `AsyncSession | None`
    # fits both cases cleanly.
    async def signup(name: str, email: str, password: str, db) -> bool:
        try:
            existing_user = await user_crud.get_by_email(email, db)

            # Hashed unconditionally so both branches take the same Argon2
            # time; skipping it on the existing-email path would let an
            # attacker distinguish emails by response latency alone.
            hashed_password = await password_service.hash_password(password)

            if existing_user:
                logger.info("Signup attempt with existing email: %s", email)
                return False

            # The baseline policy is the actual source of a new account's
            # access. Do not create an account that cannot receive it: a
            # role value is display metadata only and must never become a
            # fallback authorization path.
            self_service_policy = await policy_repository.get_by_name(SELF_SERVICE_POLICY_NAME, db)
            if not self_service_policy:
                logger.error(
                    "Default policy '%s' is missing; refusing to create signup account %s",
                    SELF_SERVICE_POLICY_NAME,
                    email,
                )
                return False

            user_data = {
                "name": name,
                "email": email,
                "hashed_password": hashed_password,
                "role": UserRole.user,      # Metadata/display only, grants nothing
                "is_verified": False,
                "is_active": True,
            }

            try:
                new_user = await user_crud.create(user_data, db)
            except IntegrityError:
                # Benign create race: another concurrent signup for the same
                # email won between our existing_user check above and this
                # insert. The unique constraint on users.email is what
                # actually prevents the duplicate, not the check-then-act
                # above (which is inherently racy). Not an unexpected
                # failure, so it's logged at info, not error/traceback.
                await db.rollback()
                logger.info("Signup lost a create race for %s, treating as already-registered", email)
                return False

            # Assign the baseline self-service policy: the actual source of
            # this account's access, per PBAC.
            try:
                await policy_repository.assign_policy_to_user(
                    user_id=new_user.id, policy_id=self_service_policy.id, db=db, assigned_by="system"
                )
            except Exception:
                # The CRUD helpers commit independently, so use a
                # compensating delete if assignment fails after the user row
                # has committed. This keeps an account with no baseline PBAC
                # access from surviving a partial signup.
                logger.error(
                    "Default policy '%s' could not be assigned; rolling back signup account %s",
                    SELF_SERVICE_POLICY_NAME, email,
                )
                try:
                    await user_crud.delete(new_user, db)
                except Exception:
                    logger.critical(
                        "Signup rollback failed for %s after default policy assignment failed",
                        email,
                        exc_info=True,
                    )
                return False

            return True

        except Exception:
            logger.error("Error during signup:\n%s", traceback.format_exc())
            return False


signup_service = SignupService()
