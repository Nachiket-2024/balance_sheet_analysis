import traceback

# Server clock for a fail-closed batch-item decision's timestamp, never
# caller-supplied.
from datetime import UTC, datetime

from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.errors import AppError
from ...logging.logging_config import get_logger
from ..evaluators.authorization_decision import AuthorizationDecision
from ..evaluators.policy_evaluator import policy_evaluation_engine
from ..models.policy_model import Policy
from ..repositories.authorization_audit_log_repository import authorization_audit_log_repository
from ..repositories.policy_repository import policy_repository
from ..repositories.user_permission_repository import user_permission_repository
from .authorization_audit_logger import build_audit_entry, log_decision
from .authorization_grant_guard import assert_authorized_to_grant

logger = get_logger(__name__)


class AuthorizationService:
    """
    The centralized authorization layer every protected route and
    business service must go through. Routes and services never decide
    authorization themselves; they call authorize()/require() with
    (user, action, resource, context), and this service fetches the
    user's policies and asks the evaluation engine for a decision.
    Nothing above this layer reads roles or does its own permission
    comparisons.
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
        (optionally scoped to `resource`/`context`), False otherwise.
        `user_email` is the acting user's identity; role never drives the
        decision.

        Thin bool wrapper over authorize_with_decision (mirrors
        PolicyEvaluationEngine.evaluate over evaluate_detailed): one
        compute-and-log code path, so a single check and a batch-of-one
        check always produce identical results.
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
        AuthorizationDecision instead of a bare bool, for callers that
        need the explanation too (e.g. batch-check's per-item
        denial_reason). Unlike authorize_detailed (below), this always
        logs an audit entry since it's a real decision.

        Logging happens here rather than inside authorize_detailed so the
        inspection endpoint, which calls authorize_detailed directly for
        a hypothetical "what would happen if" query, never pollutes the
        audit trail.
        """
        decision = await AuthorizationService.authorize_detailed(
            user_email, action, resource_type, db, resource=resource, context=context
        )

        await log_decision(user_email, action, resource_type, resource, context, decision)

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
        """Same inputs as authorize(), but returns the full
        AuthorizationDecision rather than a bool. Used by the inspection
        endpoint and by log_decision's audit trail."""
        policies = await AuthorizationService._get_effective_policies(user_email, db)

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
        Evaluates many `{"action", "resource_type", "resource"}` checks
        for one caller's own effective authorization, sharing `context`
        across every check since they all describe the same request.

        Fetches the user's active, assigned policies exactly once and
        reuses that list for every check, avoiding repeated queries. The
        evaluation logic itself is the same evaluate_detailed call
        authorize_detailed makes, so a batch-of-one always agrees with a
        single authorize() call.

        Fails closed per item: if evaluating one check raises (e.g. a
        corrupt policy row), that item becomes a denied decision with
        denial_reason "evaluation_error" rather than crashing the batch.

        Returns one decision per input check, in order. Every check's
        audit entry is written in one bulk insert after the whole batch
        is evaluated, rather than one commit per check, since a batch of
        up to 50 checks would otherwise mean 50 sequential DB round trips
        for a single request.
        """
        policies = await AuthorizationService._get_effective_policies(user_email, db)

        decisions: list[AuthorizationDecision] = []
        audit_entries: list[dict] = []
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

            audit_entries.append(
                build_audit_entry(user_email, action, resource_type, resource, context, decision)
            )
            decisions.append(decision)

        try:
            await authorization_audit_log_repository.create_entries(audit_entries, db)
        except Exception:
            # Same "never break the real decision" guarantee as log_decision:
            # the caller already has every decision above regardless of
            # whether the audit write succeeded.
            logger.warning("Failed to write batch authorization audit log entries:\n%s", traceback.format_exc())

        return decisions

    @staticmethod
    async def _get_effective_policies(user_email: str, db: AsyncSession) -> list[Policy]:
        """
        Everything the evaluation engine should treat as a grant for this
        user: their assigned, active Policy rows plus their direct
        UserPermission grants, normalized into transient, unpersisted
        Policy objects (never db.add()-ed) so evaluate_detailed needs no
        changes; it already only reads .name/.actions/.resource_type/
        .conditions. Named "direct:{action}" so decision output stays
        distinguishable from a real named policy.

        Shared by authorize_detailed and authorize_batch, which fetches
        it once and reuses it across the whole batch.
        """
        policies = await policy_repository.get_active_policies_for_user(user_email, db)
        direct_grants = await user_permission_repository.get_active_permissions_for_user(user_email, db)

        synthetic_policies = [
            Policy(
                name=f"direct:{grant.action}",
                actions=[grant.action],
                resource_type=grant.resource_type,
                conditions=grant.conditions,
                is_active=True,
            )
            for grant in direct_grants
        ]

        return policies + synthetic_policies

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
            raise AppError(
                status_code=status.HTTP_403_FORBIDDEN,
                code="INSUFFICIENT_PERMISSIONS",
                detail="Insufficient permissions",
            )

    # Privilege-escalation guard, defined in authorization_grant_guard.py;
    # re-exported here so existing call sites keep working unchanged.
    assert_authorized_to_grant = staticmethod(assert_authorized_to_grant)


authorization_service = AuthorizationService()
