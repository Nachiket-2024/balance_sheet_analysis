from dataclasses import dataclass, field


@dataclass(frozen=True)
class AuthorizationDecision:
    """
    The full explanation behind one authorization decision, produced by
    PolicyEvaluationEngine.evaluate_detailed. Lets "why was this denied"
    be answered directly (operator inspection, audit logging, tests)
    instead of re-tracing policies/conditions by hand. The engine also
    exposes a bare-bool `evaluate()` for the real authorize() hot path;
    this richer object is only for the "detailed" mode.

    Fields:
        allowed: True iff matched_policies is non-empty.
        action: The action identifier that was checked.
        resource_type: The resource type the action targets.
        user: The acting user's email.
        evaluated_policies: Every policy name the engine considered,
            whether or not it matched action/resource_type.
        matched_policies: Subset that matched AND passed conditions,
            i.e. what actually granted access. Non-empty iff allowed.
        matched_policy_conditions: Conditions attached to each granting
            policy. Internal delegation checks use this to prevent a
            conditional grant from being widened without exposing it in API
            responses.
        rejected_policies: Subset that matched but failed conditions
            ("almost, but no"), useful for diagnosing a non-trivial deny.
        failed_conditions: {policy_name: [condition_key, ...]} for each
            rejected policy, naming exactly which condition(s) failed.
        denial_reason: None if allowed, else one of
            "no_assigned_policies", "no_matching_policy", or
            "condition_failed".
        evaluation_timestamp: ISO 8601 UTC, from the engine's own clock,
            never caller-supplied.
    """

    allowed: bool
    action: str
    resource_type: str
    user: str
    evaluated_policies: list[str] = field(default_factory=list)
    matched_policies: list[str] = field(default_factory=list)
    matched_policy_conditions: dict[str, dict | None] = field(default_factory=dict, repr=False)
    rejected_policies: list[str] = field(default_factory=list)
    failed_conditions: dict[str, list[str]] = field(default_factory=dict)
    denial_reason: str | None = None
    evaluation_timestamp: str = ""
