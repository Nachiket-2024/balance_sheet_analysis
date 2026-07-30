from dataclasses import dataclass, field


@dataclass(frozen=True)
class AuthorizationDecision:
    """
    The full explanation behind one authorization decision, produced by
    PolicyEvaluationEngine.evaluate_detailed, per claude.md's Authorization
    Decision Explainability architecture:

        AuthorizationService -> PolicyEvaluationEngine -> AuthorizationDecision

    Exists so debugging "why was this denied" never requires manually
    re-tracing policies/conditions: the answer is already computed, right
    here, every time a detailed evaluation is requested (admin inspection,
    audit logging, tests). The engine still exposes a bare-bool `evaluate()`
    for the hot path (every real authorize() call); this richer object is
    for the "detailed" mode requirements ask for, not a replacement for it.

    Fields:
        allowed: The final decision: True iff matched_policies is
            non-empty.
        action: The action identifier that was checked.
        resource_type: The resource type the action targets.
        user: The acting user's email.
        evaluated_policies: Every policy's name the engine was given to
            consider, regardless of whether it even matched action/
            resource_type: "the full set of policies this user held at
            evaluation time".
        matched_policies: The subset of evaluated_policies whose
            action+resource_type matched AND whose conditions passed,
            i.e. what actually granted access. Non-empty iff allowed.
        rejected_policies: The subset whose action+resource_type matched
            but whose conditions did not pass: "almost, but no" policies,
            useful for diagnosing a deny that isn't simply "no policy for
            this at all".
        failed_conditions: {policy_name: [condition_key, ...]} for every
            policy in rejected_policies: exactly which condition key(s)
            on that policy failed (e.g. "time", "network"), not just that
            *something* did.
        denial_reason: None if allowed. Otherwise a short, machine-
            readable classification of why not, one of
            "no_assigned_policies" (the user had zero policies to
            evaluate at all), "no_matching_policy" (some policies existed,
            but none matched this action+resource_type), or
            "condition_failed" (a matching policy existed, but its
            conditions rejected this specific resource/context).
        evaluation_timestamp: ISO 8601 UTC timestamp of when this decision
            was computed (the engine's own clock, see
            policy_evaluator.py, never anything caller-supplied).
    """

    allowed: bool
    action: str
    resource_type: str
    user: str
    evaluated_policies: list[str] = field(default_factory=list)
    matched_policies: list[str] = field(default_factory=list)
    rejected_policies: list[str] = field(default_factory=list)
    failed_conditions: dict[str, list[str]] = field(default_factory=dict)
    denial_reason: str | None = None
    evaluation_timestamp: str = ""
