from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.errors import AppError
from ..permissions import Permission
from ..policies.default_policies import SYSTEM_SUPERUSER_POLICY_NAME
from ..repositories.policy_assignment_repository import policy_assignment_repository


async def assert_authorized_to_grant(
    caller_email: str,
    actions: list[str],
    resource_type: str,
    db: AsyncSession,
    context: dict | None = None,
    conditions: dict | None = None,
    cache: dict[tuple[str, str], bool] | None = None,
) -> None:
    """
    Guards against privilege escalation. `caller_email` is the user
    creating/updating/assigning a policy; `actions` is the full set of
    actions that would end up granted. Every action confirms that the caller
    already holds it, raising HTTP 403 on the first one they don't. This
    includes downstream app actions such as "projects:read": the
    authorization layer treats action identifiers as opaque strings, so it can
    enforce the same anti-escalation rule without owning the app's vocabulary.

    `conditions` is the condition block that will be granted. A caller may
    delegate an unconditional action only when one of their matching grants
    is unconditional. For a conditional grant, every condition in the
    caller's matching grant must be preserved exactly; extra conditions are
    allowed because they narrow access. This prevents a network- or
    ownership-limited operator from minting a broader grant.

    `context` should be the same request context the route's own
    require_authorization dependency built. Without it, the "do you
    already hold this" check evaluates with no IP/time/security_context,
    failing closed for a caller who holds the action only via a
    context-dependent policy (e.g. network- or time-restricted). Callers
    with no real request (background tasks) can omit it; that's
    conservative (may under-grant, never over-grants).

    The caller must receive an app's first custom action through a trusted
    bootstrap path, normally an app-owned migration or seed policy. A caller
    with only policies:create/assign cannot mint an arbitrary custom policy
    and assign it to themselves.

    Imports AuthorizationService locally to avoid a circular import
    (authorization_service.py delegates its own assert_authorized_to_grant
    here).

    `cache`, when given, is an (action, resource_type) -> allowed dict the
    caller reuses across repeated calls in the same request (e.g. a
    bulk-assign loop). Safe to memoize without a TTL since caller_email
    and context are fixed for the request's duration; avoids re-running
    evaluation for the same action across many bulk items.
    """
    from .authorization_service import AuthorizationService

    # The protected system_superuser policy is the trusted bootstrap path for
    # app-owned actions. This remains policy-based, not role-based: only a
    # caller who actually holds the protected policy gets this capability.
    built_in_actions = frozenset(permission.value for permission in Permission)
    is_system_superuser = False
    if any(action not in built_in_actions for action in actions):
        active_policies = await policy_assignment_repository.get_active_policies_for_user(caller_email, db)
        is_system_superuser = any(policy.name == SYSTEM_SUPERUSER_POLICY_NAME for policy in active_policies)

    for action in actions:
        cache_key = (action, resource_type)
        # A cached boolean is safe only for an unconditional proposal. A
        # bulk request may reuse an action with different condition blocks,
        # so conditioned proposals always get a fresh decision containing
        # the granting policies' conditions.
        use_cache = not conditions
        if use_cache and cache is not None and cache_key in cache:
            allowed = cache[cache_key]
            decision = None
        else:
            if is_system_superuser:
                decision = None
                allowed = True
            else:
                decision = await AuthorizationService.authorize_with_decision(
                    caller_email, action, resource_type, db, context=context
                )
                allowed = decision.allowed
            if use_cache and cache is not None:
                cache[cache_key] = allowed
        if not allowed:
            raise AppError(
                status_code=status.HTTP_403_FORBIDDEN,
                code="CANNOT_GRANT_UNHELD_ACTION",
                detail=f"Cannot grant action '{action}': you do not hold it yourself",
                params={"action": action},
            )

        if not is_system_superuser and decision is not None and not _has_scope_for_grant(
            decision.matched_policy_conditions, conditions
        ):
            raise AppError(
                status_code=status.HTTP_403_FORBIDDEN,
                code="CANNOT_GRANT_BROADER_CONDITIONS",
                detail=f"Cannot grant action '{action}' with broader conditions than your own",
                params={"action": action},
            )


def _has_scope_for_grant(
    matched_policy_conditions: dict[str, dict | None],
    proposed_conditions: dict | None,
) -> bool:
    """Return whether one matching caller grant contains the proposal.

    Condition handlers are extensible and some values have domain-specific
    subset semantics. Exact preservation of the caller's values is the safe
    common denominator; adding another top-level condition can only narrow
    the resulting grant. An unconditional caller grant can delegate any
    condition block.
    """
    for source_conditions in matched_policy_conditions.values():
        source = source_conditions or {}
        proposed = proposed_conditions or {}
        if not source or all(proposed.get(key) == value for key, value in source.items()):
            return True
    return False
