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
    The single place authorization decisions are computed. Pure and
    DB-free: takes a user's already-fetched policies and answers "do any
    of these allow this action on this resource, given this context?"
    without knowing how those policies were fetched or what a route is.
    Keeps the engine trivially unit-testable and reusable from anywhere
    (routes, background jobs, inspection endpoints).

    Decision rule: default-deny; ALLOW if at least one active, applicable
    policy's conditions are satisfied. No explicit-deny policy concept:
    every policy is a grant, so zero applicable policies means deny.

    Only matches action/resource_type itself, then delegates a policy's
    whole `conditions` block to ConditionEvaluationService. Adding a new
    condition type never requires touching this class.
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
        policies; this engine does not re-check that. `user_email` is used
        only for ownership-style conditions ("self_only"), never to look
        up a role. `resource` is the resource instance being acted on, if
        any; `context` carries request metadata needed for
        "context_attributes" conditions.

        Returns True if any matching policy's conditions are satisfied,
        False (default-deny) otherwise, including when `policies` is
        empty.

        Thin wrapper over evaluate_detailed's `.allowed`: the extra
        explainability bookkeeping is cheap relative to a DB round trip,
        so there's one evaluation code path, not two.
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
        """Same inputs as evaluate(), but returns a full
        AuthorizationDecision explaining which policies were in play,
        which granted access, which failed and on what condition, and a
        machine-readable denial reason. Powers the authorization-check
        endpoint, audit logging, and tests."""
        evaluated_policies: list[str] = [policy.name for policy in policies]
        matched_policies: list[str] = []
        matched_policy_conditions: dict[str, dict | None] = {}
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
                matched_policy_conditions[policy.name] = policy.conditions
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
            matched_policy_conditions=matched_policy_conditions,
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
