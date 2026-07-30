import asyncio

from ..authorization.repositories.policy_repository import policy_repository
from ..database.connection import database
from ..logging.logging_config import get_logger

logger = get_logger(__name__)

ROLE_POLICY_PREFIX = "role_"


def _policy_name_for_role(role_name: str) -> str:
    return f"{ROLE_POLICY_PREFIX}{role_name.strip().lower().replace(' ', '_')}"


async def create_rbac_policy():
    """
    Interactive CLI script to seed one unconditioned, RBAC-shaped policy :
    "everyone holding this role gets exactly this action list, with no
    per-resource scoping" : for downstream projects that don't need PBAC's
    full conditions/resource_attributes generality. See
    docs/mystic_auth/authorization/rbac-quickstart.md for the concept this
    implements: a policy with no `conditions` at all is already RBAC, the
    same shape this template's own seeded `self_service`/
    `user_administration`/`system_superuser` baseline policies already use
    (see docs/mystic_auth/authorization/policy-examples.md).

    Does NOT touch `users.role` : that column stays exactly what it always
    was, display/grouping metadata only (see
    docs/mystic_auth/authorization/adding-permissions.md#roles-vs-policies).
    Actual access still comes entirely from the policy this script creates,
    assigned to whichever users should hold it : via the `/policies` UI, or
    `POST /authorization/users/{email}/policies`, same as any other policy.

    Idempotent by name: if a policy named `role_<role>` already exists, this
    prints its current actions and exits without changing anything : use
    `PUT /authorization/policies/{id}` (or the UI) to edit it instead of
    re-running this script.

    Deliberately CLI-only, same reasoning as create_system_user.py : no API
    endpoint bypasses the privilege-escalation guard this way, so this stays
    an explicit operator action.

    Run interactively:
        python -m mystic_auth.scripts.create_rbac_policies
    """
    print("\n--- RBAC-Shaped Policy Creation ---")
    print("Creates one unconditioned policy: every user assigned it gets exactly")
    print("the actions you list below, with no per-resource scoping.")
    print("See docs/mystic_auth/authorization/rbac-quickstart.md for the concept.\n")

    role_name = input("Role name (e.g. 'editor', 'viewer'): ").strip()
    if not role_name:
        print("\n Aborted : role name cannot be empty.")
        return

    policy_name = _policy_name_for_role(role_name)

    resource_type = input("Resource type this role applies to (or '*' for all): ").strip() or "*"

    actions_raw = input(
        "Actions this role grants, comma-separated (e.g. 'documents:view,documents:edit'): "
    ).strip()
    actions = [a.strip() for a in actions_raw.split(",") if a.strip()]
    if not actions:
        print("\n Aborted : at least one action is required.")
        return

    description = input("Description (optional): ").strip() or None

    async for db in database.get_session():
        existing = await policy_repository.get_by_name(policy_name, db)
        if existing:
            print(
                f"\n Policy '{policy_name}' already exists with actions {existing.actions} : "
                "no changes made. Edit it via PUT /authorization/policies/{id} or the /policies UI instead."
            )
            logger.info("RBAC policy creation skipped, already exists: %s", policy_name)
            return

        policy = await policy_repository.create(
            {
                "name": policy_name,
                "description": description,
                "actions": actions,
                "resource_type": resource_type,
                "conditions": None,
                "is_active": True,
            },
            db,
            changed_by="system",
        )

        print(f"\n Policy '{policy.name}' created : grants {actions} on '{resource_type}'.")
        print(" Assign it to users via the /policies UI or POST /authorization/users/{email}/policies.")
        logger.info("RBAC policy created via CLI: %s", policy.name)
        return


if __name__ == "__main__":
    asyncio.run(create_rbac_policy())
