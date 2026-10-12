import asyncio
from collections import defaultdict

from sqlalchemy import select

from ..authorization.models.policy_model import UserPolicy
from ..authorization.models.user_permission_model import UserPermission
from ..authorization.services.authorization_service import AuthorizationService
from ..database.connection import database
from ..logging.logging_config import get_logger
from ..user.user_model import User

logger = get_logger(__name__)


async def _users_with_any_grant(db) -> list[str]:
    """Every email holding at least one active policy or direct
    permission - the only users a conflict could even apply to."""
    policy_emails = await db.execute(
        select(User.email).join(UserPolicy, UserPolicy.user_id == User.id).distinct()
    )
    permission_emails = await db.execute(
        select(User.email)
        .join(UserPermission, UserPermission.user_id == User.id)
        .where(UserPermission.is_active.is_(True))
        .distinct()
    )
    return sorted({*policy_emails.scalars(), *permission_emails.scalars()})


async def _report() -> list[dict]:
    """
    Pure OR semantics across every policy and direct permission a user
    holds (authorization_service.py::_get_effective_policies,
    policy_evaluator.py::evaluate_detailed) means a conditioned grant is
    not a hard ceiling on an action: it only actually restricts a user if
    it's the *only* grant they hold for that (action, resource_type). Any
    other grant for the same pair - conditioned or not, a policy or a
    direct permission, added by a different admin at a different time -
    silently makes the restriction moot, with no warning anywhere in the
    UI or API. This read-only report surfaces exactly that: it changes
    no authorization behavior, and
    grant-time itself is deliberately left alone (whether two grants
    should ever be allowed to coexist like this is a policy call each
    deployment makes for itself, not something this script decides).

    Run via:
        python -m mystic_auth.scripts.report_conditioned_grant_conflicts
    """
    findings: list[dict] = []
    async for db in database.get_session():
        emails = await _users_with_any_grant(db)
        for email in emails:
            effective = await AuthorizationService._get_effective_policies(email, db)
            by_action: dict[tuple[str, str], list] = defaultdict(list)
            for grant in effective:
                for action in grant.actions or []:
                    by_action[(action, grant.resource_type)].append(grant)

            for (action, resource_type), grants in by_action.items():
                has_unconditioned = any(not g.conditions for g in grants)
                has_conditioned = any(g.conditions for g in grants)
                if has_unconditioned and has_conditioned and len(grants) > 1:
                    findings.append({
                        "user_email": email,
                        "action": action,
                        "resource_type": resource_type,
                        "sources": [g.name for g in grants],
                    })
    return findings


def main() -> None:
    findings = asyncio.run(_report())
    if not findings:
        print("No conflicts found: no user holds both a conditioned and an unconditioned grant for the same action.")
        return

    print(f"Found {len(findings)} conditioned/unconditioned grant conflict(s):\n")
    for f in findings:
        print(f"  {f['user_email']}: '{f['action']}' on '{f['resource_type']}' - held via {f['sources']}")
    print(
        "\nEach of these users has at least one unconditioned grant alongside a conditioned one for the "
        "same action - the conditioned grant's restriction is not actually in effect for them. See "
        "docs/mystic_auth/authorization/architecture/component-responsibilities.md "
        "(Policy Evaluation Engine) for the full explanation."
    )


if __name__ == "__main__":
    main()
