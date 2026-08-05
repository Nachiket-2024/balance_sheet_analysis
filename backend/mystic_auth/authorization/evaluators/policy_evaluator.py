from datetime import UTC, datetime

# This engine delegates condition-key logic to the condition-handler layer:
# PolicyEvaluationEngine -> ConditionEvaluationService -> ConditionHandler.
from ..conditions.condition_evaluation_service import condition_evaluation_service

# evaluate() takes already-fetched Policy rows so this module has no DB
# dependency of its own (see PolicyEvaluationEngine's docstring).
from ..models.policy_model import Policy
from .authorization_decision import AuthorizationDecision


class PolicyEvaluationEngine:
    """
    The single place authorization decisions are actually computed. Pure
    and DB-free by design: it takes a user's already-fetched policies (the
    repository's job) and answers one question: "do any of these policies
    allow this action on this resource, given this context?", without
    knowing how those policies were fetched or what a route is.

    This keeps the engine trivially unit-testable (no DB, no FastAPI, no
    mocking, just Policy objects in, bool out) and reusable from anywhere
    (routes via the authorization service/dependency, background jobs,
    management APIs computing "effective authorization" for inspection).

    Decision rule: default-deny; ALLOW if at least one active, applicable
    policy's conditions are satisfied. There is currently no explicit-deny
    policy concept. Allow/Deny is the evaluation outcome, not a pair of
    competing policy types. Every policy is a grant, and having zero
    applicable policies naturally means "deny".

    This engine only matches action/resource_type and then delegates a
    policy's whole `conditions` block to ConditionEvaluationService: it
    contains no condition-specific logic itself (see
    conditions/condition_handler.py): Authorization Engine -> Condition
    Evaluation Service -> Condition Handlers. Adding a new condition type
    (see conditions/) never requires touching this class.
    """

    @staticmethod
    def evaluate(
        policies: list[Policy],
        action: str,
        resource_type: str,
        user_email: str,
        resource: dict | object | None = None,
        context: dict | None = None,
    ) -> bool:
        """
        `policies` must already be filtered to the user's active, assigned
        policies (is_active=True); this engine does not re-check that.
        `user_email` is used only for ownership-style conditions (e.g.
        "self_only"), never to look up a role. `resource` is the specific
        resource instance being acted on, if any, needed to evaluate
        ownership or resource-state conditions; `context` carries
        additional contextual information (e.g. request metadata) needed
        for "context_attributes" conditions (e.g. an MFA-gated action).

        Returns True if any policy whose resource_type + action matches has
        satisfied conditions, False (default-deny) otherwise, including
        when `policies` is empty.

        Thin wrapper over evaluate_detailed's `.allowed`; this is the fast
        path every real authorize() call goes through; evaluate_detailed's
        extra explainability bookkeeping (failed_conditions,
        denial_reason, ...) is cheap relative to a DB round trip, so there
        is one evaluation code path, not two. This keeps the hot path fast
        without duplicating permission logic.
        """
        return PolicyEvaluationEngine.evaluate_detailed(
            policies, action, resource_type, user_email, resource, context
        ).allowed

    @staticmethod
    def evaluate_detailed(
        policies: list[Policy],
        action: str,
        resource_type: str,
        user_email: str,
        resource: dict | object | None = None,
        context: dict | None = None,
    ) -> AuthorizationDecision:
        """
        Same inputs as evaluate(), but returns a full AuthorizationDecision
        (see authorization_decision.py) explaining the decision rather than
        just a bool; this is what powers the authorization-check endpoint,
        audit logging, and tests. It explains not just *whether* access was granted, but *which*
        policies were even in play, which of those actually granted it,
        which failed and on what condition, and a machine-readable reason
        when denied.
        """
        evaluated_policies: list[str] = [policy.name for policy in policies]
        matched_policies: list[str] = []
        rejected_policies: list[str] = []
        failed_conditions: dict[str, list[str]] = {}

        for policy in policies:
            # Resource type must match (or the policy is resource-agnostic)
            if policy.resource_type not in (resource_type, "*"):
                continue

            if action not in (policy.actions or []):
                continue

            condition_result = condition_evaluation_service.evaluate_detailed(
                policy.conditions, user_email, resource, context
            )
            if condition_result["satisfied"]:
                matched_policies.append(policy.name)
            else:
                rejected_policies.append(policy.name)
                failed_conditions[policy.name] = condition_result["failed_keys"]

        allowed = len(matched_policies) > 0

        return AuthorizationDecision(
            allowed=allowed,
            action=action,
            resource_type=resource_type,
            user=user_email,
            evaluated_policies=evaluated_policies,
            matched_policies=matched_policies,
            rejected_policies=rejected_policies,
            failed_conditions=failed_conditions,
            denial_reason=None if allowed else PolicyEvaluationEngine._denial_reason(
                evaluated_policies, matched_policies, rejected_policies
            ),
            evaluation_timestamp=datetime.now(UTC).isoformat(),
        )

    @staticmethod
    def _denial_reason(
        evaluated_policies: list[str],
        matched_policies: list[str],
        rejected_policies: list[str],
    ) -> str:
        """
        A short, machine-readable classification of why access was denied
        only ever called when matched_policies is empty (i.e. denied).

        - "no_assigned_policies": the user had zero active policies to
          evaluate at all.
        - "no_matching_policy": policies existed, but none matched this
          action+resource_type (rejected_policies is also empty).
        - "condition_failed": at least one policy matched action+
          resource_type, but its conditions rejected this specific
          resource/context.
        """
        if not evaluated_policies:
            return "no_assigned_policies"
        if not rejected_policies:
            return "no_matching_policy"
        return "condition_failed"


policy_evaluation_engine = PolicyEvaluationEngine()
