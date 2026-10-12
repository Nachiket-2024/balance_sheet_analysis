from backend.mystic_auth.authorization.evaluators.authorization_decision import (
    AuthorizationDecision,
)


def authorization_decision(allowed: bool, matched_policy_conditions: dict[str, dict | None] | None = None) -> AuthorizationDecision:
    """Build a minimal detailed decision for route unit-test boundaries."""
    return AuthorizationDecision(
        allowed=allowed,
        action="test:action",
        resource_type="test_resource",
        user="caller@example.com",
        matched_policy_conditions=(matched_policy_conditions or {"test_policy": None}) if allowed else {},
    )
