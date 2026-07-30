import traceback

# Server clock for a fail-closed batch-item decision's timestamp, never
# anything caller-supplied (see context/request_context_builder.py)
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...logging.logging_config import get_logger
from ..evaluators.authorization_decision import AuthorizationDecision
from ..evaluators.policy_evaluator import policy_evaluation_engine

# The app's own fixed, known-sensitive action vocabulary: see
# assert_authorized_to_grant for why only these are escalation-guarded.
from ..permissions import Permission
from ..repositories.audit_log_repository import audit_log_repository
from ..repositories.policy_repository import policy_repository

logger = get_logger(__name__)

# Actions this app itself defines and knows to be sensitive (identity and
# authorization-management actions, see permissions.py). Only these are
# subject to the privilege-escalation guard below; see that method's
# docstring for why arbitrary other action strings are deliberately exempt.
_KNOWN_SENSITIVE_ACTIONS = frozenset(permission.value for permission in Permission)


class AuthorizationService:
    """
    The centralized authorization layer every protected route and business
    service must go through:

        Request -> Authentication -> Authorization Service
                -> Policy Evaluation Engine -> Allow / Deny

    Routes and services never decide authorization themselves; they call
    authorize()/require() here with (user, action, resource, context), and
    this service owns fetching the user's policies and asking the
    evaluation engine for a decision. Nothing above this layer (routes,
    other services) reads roles, permission-role mappings, or does its own
    role/permission comparisons.
    """

    @staticmethod
    async def authorize(
        user_email: str,
        action: str,
        resource_type: str,
        db: AsyncSession,
        resource: dict | object | None = None,
        context: dict | None = None,
    ) -> bool:
        """
        True if `user_email` is authorized for `action` on `resource_type`
        (optionally scoped to a specific `resource`/`context`), False
        otherwise. `user_email` is the acting user's identity, never their
        role; role must never drive an authorization decision here.

        Delegates entirely to authorize_with_decision (computes the
        decision and logs it) and returns just `.allowed`, a thin bool
        wrapper, mirroring PolicyEvaluationEngine.evaluate being a thin
        wrapper over evaluate_detailed. One compute-and-log code path, not
        two: the batch endpoint's authorize_batch reuses this same path
        per check (see below), so a single check and a batch-of-one check
        always produce and log an identical decision.
        """
        decision = await AuthorizationService.authorize_with_decision(
            user_email, action, resource_type, db, resource=resource, context=context
        )
        return decision.allowed

    @staticmethod
    async def authorize_with_decision(
        user_email: str,
        action: str,
        resource_type: str,
        db: AsyncSession,
        resource: dict | object | None = None,
        context: dict | None = None,
    ) -> AuthorizationDecision:
        """
        Same inputs as authorize(), but returns the full
        AuthorizationDecision instead of a bare bool, used wherever a real
        (not hypothetical) authorization decision needs its explanation
        too, e.g. the batch-check endpoint reporting a per-item
        denial_reason. Unlike authorize_detailed (below), this always logs
        an audit entry: it represents a real decision something is about
        to act on, exactly like authorize() does, because authorize() is
        now just `.allowed` off of this same call.

        The decision is computed via authorize_detailed (fetches the user's
        active, assigned policies and asks the evaluation engine), then
        logged here rather than inside authorize_detailed itself, so the
        authorization-check inspection endpoint (which calls
        authorize_detailed directly for a hypothetical "what would happen
        if" query) never pollutes the audit trail with decisions nothing
        actually acted on.
        """
        decision = await AuthorizationService.authorize_detailed(
            user_email, action, resource_type, db, resource=resource, context=context
        )

        await AuthorizationService._log_decision(
            user_email, action, resource_type, resource, context, decision, db
        )

        return decision

    @staticmethod
    async def authorize_detailed(
        user_email: str,
        action: str,
        resource_type: str,
        db: AsyncSession,
        resource: dict | object | None = None,
        context: dict | None = None,
    ) -> AuthorizationDecision:
        """
        Same inputs as authorize(), but returns the full
        AuthorizationDecision from PolicyEvaluationEngine.evaluate_detailed
        rather than just a bool, used by the authorization-check
        inspection endpoint (api/pbac_routes/authorization_check_routes.py)
        and by _log_decision's audit trail. See evaluators/authorization_decision.py
        for the decision shape.
        """
        policies = await policy_repository.get_active_policies_for_user(user_email, db)

        return policy_evaluation_engine.evaluate_detailed(
            policies=policies,
            action=action,
            resource_type=resource_type,
            user_email=user_email,
            resource=resource,
            context=context,
        )

    @staticmethod
    async def authorize_batch(
        user_email: str,
        checks: list[dict],
        db: AsyncSession,
        context: dict | None = None,
    ) -> list[AuthorizationDecision]:
        """
        Evaluates many `{"action", "resource_type", "resource"}` checks for
        one caller's own effective authorization (there is no per-item
        target user), sharing `context` (the one real request context, see
        context/request_context_builder.py) across every check, since they
        all describe the same single incoming request.

        Fetches the user's active, assigned policies exactly once and
        reuses that list for every check below, avoiding repeated policy
        database queries within one batch request. That's the only
        difference from calling authorize_with_decision N times (which
        would re-fetch on every call); the evaluation logic itself is the
        identical PolicyEvaluationEngine.evaluate_detailed call
        authorize_detailed also makes, so a batch-of-one check always
        agrees with a single authorize() call for the same input. Each
        check's decision is logged individually, same as
        authorize_with_decision, just without re-fetching.

        Fails closed per item: if evaluating one check somehow raises (e.g.
        a corrupt policy row), that item becomes a denied decision with
        denial_reason "evaluation_error" rather than crashing the rest of
        the batch or defaulting to allowed.

        Returns one decision per input check, in the same order; the
        route layer decides how much of each to expose (see
        api/pbac_routes/authorization_check_routes.py, which deliberately surfaces only
        allowed/denial_reason, never matched/rejected/failed_conditions,
        for a batch response).
        """
        policies = await policy_repository.get_active_policies_for_user(user_email, db)

        decisions: list[AuthorizationDecision] = []
        for check in checks:
            action = check["action"]
            resource_type = check["resource_type"]
            resource = check.get("resource")

            try:
                decision = policy_evaluation_engine.evaluate_detailed(
                    policies=policies,
                    action=action,
                    resource_type=resource_type,
                    user_email=user_email,
                    resource=resource,
                    context=context,
                )
            except Exception:
                logger.warning(
                    "Batch authorization check failed to evaluate (action=%s, resource_type=%s):\n%s",
                    action, resource_type, traceback.format_exc(),
                )
                decision = AuthorizationDecision(
                    allowed=False,
                    action=action,
                    resource_type=resource_type,
                    user=user_email,
                    denial_reason="evaluation_error",
                    evaluation_timestamp=datetime.now(UTC).isoformat(),
                )

            await AuthorizationService._log_decision(
                user_email, action, resource_type, resource, context, decision, db
            )
            decisions.append(decision)

        return decisions

    @staticmethod
    async def _log_decision(
        user_email: str,
        action: str,
        resource_type: str,
        resource: dict | object | None,
        context: dict | None,
        decision: AuthorizationDecision,
        db: AsyncSession,
    ) -> None:
        """
        Persists an audit log row for a real decision: `decision` is the
        full explanation to record, capturing not just the bare allow/deny
        but which policies matched vs. were rejected and exactly which
        condition(s) failed on the rejected ones, so "why was this denied"
        is answerable from the audit trail alone, without re-running the
        evaluation.

        A logging failure must never break the actual authorization
        decision it's describing, caught and logged as a warning here,
        never re-raised. The route/caller that asked for this decision has
        already gotten (or will get) its answer regardless of whether the
        audit write succeeded.
        """
        try:
            # resource is often an arbitrary dict/object with no guaranteed
            # key, so this is a best-effort identifier for the log entry.
            resource_identifier = None
            if isinstance(resource, dict):
                resource_identifier = resource.get("email") or resource.get("id")
            elif resource is not None:
                resource_identifier = getattr(resource, "email", None) or getattr(resource, "id", None)
            if resource_identifier is not None:
                resource_identifier = str(resource_identifier)

            await audit_log_repository.create_entry(
                {
                    "user_email": user_email,
                    "action": action,
                    "resource_type": resource_type,
                    "resource_identifier": resource_identifier,
                    "allowed": decision.allowed,
                    "candidate_policy_names": decision.matched_policies + decision.rejected_policies,
                    "granting_policy_names": decision.matched_policies,
                    "failed_conditions": decision.failed_conditions or None,
                    "context": context,
                },
                db,
            )
        except Exception:
            logger.warning("Failed to write authorization audit log entry:\n%s", traceback.format_exc())

    @staticmethod
    async def require(
        user_email: str,
        action: str,
        resource_type: str,
        db: AsyncSession,
        resource: dict | object | None = None,
        context: dict | None = None,
    ) -> None:
        """
        Same inputs as authorize(), but raises HTTP 403 instead of
        returning False; the form routes actually call (directly, or via
        dependencies.authorization_dependency.require_authorization).
        """
        allowed = await AuthorizationService.authorize(
            user_email, action, resource_type, db, resource=resource, context=context
        )
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )

    @staticmethod
    async def assert_authorized_to_grant(
        caller_email: str,
        actions: list[str],
        resource_type: str,
        db: AsyncSession,
    ) -> None:
        """
        Guards against privilege escalation: `caller_email` is the user
        attempting to create/update a policy, or assign one to someone
        (possibly themselves), and `actions` is the full set of actions
        that would end up granted as a result. For every action in
        `actions` that is one of this app's own known-sensitive actions
        (Permission's fixed vocabulary, identity and authorization-
        management actions), confirms the caller is already authorized for
        it, raising HTTP 403 on the first one the caller doesn't already
        hold. Any action outside that vocabulary, an arbitrary business-
        domain action a downstream application built on this template
        defines for its own resources (e.g. "projects:read"), is skipped
        entirely.

        Creating a policy, editing a policy's actions, or assigning a
        policy to a user must never be able to hand out (to anyone,
        including the caller themselves) one of *this app's own* sensitive
        actions that the caller doesn't already have, otherwise holding
        only policies:create+policies:assign (without system_superuser
        itself) would let a caller mint an all-powerful policy and assign
        it to themselves.

        Deliberately scoped to Permission's fixed vocabulary rather than
        every action string: PBAC policies in this template are meant to
        freely grant whatever actions a downstream application defines for
        its own business resources; policies:create/assign is a
        general-purpose policy-authoring capability, not itself the
        resource being protected. Only this app's built-in identity/
        authorization actions are sensitive enough to guard here. Called
        from api/pbac_routes/policy_crud_routes.py's create/update
        endpoints and policy_assignment_routes.py's assign endpoint,
        never bypassed by going straight to the repository from a route.
        """
        for action in actions:
            if action not in _KNOWN_SENSITIVE_ACTIONS:
                continue
            allowed = await AuthorizationService.authorize(caller_email, action, resource_type, db)
            if not allowed:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Cannot grant action '{action}': you do not hold it yourself",
                )


authorization_service = AuthorizationService()
