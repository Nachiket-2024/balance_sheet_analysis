import asyncio
import getpass

from ..auth.password_logic.password_service import password_service
from ..authorization.policies.default_policies import (
    SELF_SERVICE_POLICY_NAME,
    SYSTEM_SUPERUSER_POLICY_NAME,
    USER_ADMINISTRATION_POLICY_NAME,
)

# PBAC: the system superuser's actual access comes from holding every
# baseline policy, assigned explicitly here : not from role="system".
from ..authorization.repositories.policy_repository import policy_repository
from ..database.connection import database
from ..logging.logging_config import get_logger
from ..user_crud.user_crud_collector import user_crud

# UserRole is kept as display/grouping metadata for the system account; it no
# longer grants any access itself (see PBAC policy assignment below).
from ..user_table.user_model import UserRole

logger = get_logger(__name__)

SYSTEM_ROLE = UserRole.system

# Every baseline policy the system superuser must hold, so it has strictly
# greater access than any other account (self-service + user administration +
# the system-only actions).
SYSTEM_USER_POLICY_NAMES = (
    SELF_SERVICE_POLICY_NAME,
    USER_ADMINISTRATION_POLICY_NAME,
    SYSTEM_SUPERUSER_POLICY_NAME,
)


async def _assign_system_policies(user_id: int, user_email: str, db, assigned_by: str) -> bool:
    """
    Assigns every baseline policy to `user_id` : the actual source of
    system-superuser access, per PBAC (never `role`). `assign_policy_to_user`
    is idempotent (see its own docstring), so this is safe to call against a
    user who already holds some or all of these, whether that's a fresh
    account or an existing one being promoted.

    Returns False (after printing/logging why) if a baseline policy row is
    missing entirely : migrations haven't been run : rather than assigning a
    partial set silently.
    """
    for policy_name in SYSTEM_USER_POLICY_NAMES:
        policy = await policy_repository.get_by_name(policy_name, db)
        if not policy:
            logger.error(
                "Baseline policy '%s' not found : run migrations first",
                policy_name,
            )
            print(f"\n Baseline policy '{policy_name}' not found. Run migrations first.")
            return False
        await policy_repository.assign_policy_to_user(
            user_id=user_id, policy_id=policy.id, db=db, assigned_by=assigned_by, user_email=user_email
        )
    return True


async def create_system_user():
    """
    Interactive CLI script to create the one-time system superuser : or, if
    the email you give already belongs to an existing account (e.g. someone
    who forgot to bootstrap this first and just signed up/logged in via
    Google to test), promote that account instead, after an explicit
    confirmation. Branches on whether that existing account has a password:

    - **No password at all (a Google-only account)**: can't be promoted in
      place. A system account can't use Google login (see
      docs/mystic_auth/authentication/oauth2-pkce.md's "system account is
      blocked from OAuth2 login entirely"), and this account has no password
      either : promoting it as-is would leave it with literally no way to
      log in afterward. Offers to delete that account and immediately fall
      into the normal creation flow instead (same email, fresh name/password
      prompts) : a clean account, not a half-broken one.
    - **Has a password already**: promotes in place : assigns the missing
      baseline policies (see SYSTEM_USER_POLICY_NAMES above, the actual
      source of PBAC access, never `role`), sets `role` to `system` too (not
      strictly required for access, but keeps the account's shape consistent
      with the one this script normally creates, and is what actually
      disables future Google login for it), and requires setting a new
      password as part of the promotion : the operator running this script
      may not be the one who originally set it, and a system-level account
      shouldn't rely on a password nobody currently running this can verify.

    Either way, this only ever assigns/updates rows this script's own
    operator explicitly confirmed : never a silent upsert.

    Deliberately CLI-only : there is still no API endpoint that can create or
    promote a user, by design.

    Run once manually before first launch, or any time you need to promote
    an existing account:
        python -m mystic_auth.scripts.create_system_user
    """
    print("\n--- System Superuser Creation ---")

    email = input("Enter system user email: ").strip()

    async for db in database.get_session():

        existing = await user_crud.get_by_email(email, db)

        if existing and existing.hashed_password is None:
            print(
                f"\n A user with email '{email}' already exists (name: '{existing.name}'), "
                "but it has no password : it only ever logged in via Google."
            )
            print(" A system account can't use Google login, so this account needs a password to be usable at all.")
            confirm = input(
                "Delete this Google-only account and create a fresh system user with the same email instead? [y/N]: "
            ).strip().lower()
            if confirm != "y":
                print("\n Aborted : no changes made.")
                logger.warning(
                    "System superuser promotion declined (Google-only account, no password): %s", email
                )
                return
            await user_crud.delete(existing, db)
            logger.info("Deleted Google-only account to recreate as system user: %s", email)
            existing = None

        if existing:
            print(
                f"\n A user with email '{email}' already exists "
                f"(name: '{existing.name}', current role: '{existing.role.value}')."
            )
            print(
                " Promoting will also set this account's role to 'system' : Google login (if this account "
                "ever used it) will stop working afterward; only a password will."
            )
            confirm = input("Promote this existing user to system superuser? [y/N]: ").strip().lower()
            if confirm != "y":
                print("\n Aborted : no changes made.")
                logger.warning(
                    "System superuser promotion declined for existing email: %s", email
                )
                return

            if not await _assign_system_policies(existing.id, existing.email, db, assigned_by="system"):
                return

            new_password = getpass.getpass("Set a new password for this account: ")
            hashed_password = await password_service.hash_password(new_password)
            await user_crud.update(existing, {"role": SYSTEM_ROLE, "hashed_password": hashed_password}, db)

            print(
                f"\n Existing user '{email}' promoted to system superuser. Role set to 'system' : "
                "Google login will no longer work for this account; use the new password instead."
            )
            logger.info("Existing user promoted to system superuser via CLI: %s", email)
            return

        name     = input("Enter system user name: ").strip()
        password = getpass.getpass("Enter system user password: ")

        hashed_password = await password_service.hash_password(password)

        new_user = await user_crud.create({
            "name":            name,
            "email":           email,
            "hashed_password": hashed_password,
            "role":            SYSTEM_ROLE,   # Display/grouping metadata only
            "is_verified":     True,          # No email verification needed for system user
            "is_active":       True,          # Fully active from the moment of creation
        }, db)

        if not await _assign_system_policies(new_user.id, new_user.email, db, assigned_by="system"):
            return

        print(f"\n System user '{email}' created successfully.")
        logger.info("System user created successfully: %s", email)


if __name__ == "__main__":
    asyncio.run(create_system_user())
