from ..condition_handler import ConditionHandler


class SecurityContextCondition(ConditionHandler):
    """
    "security_context": {"device_trusted": true, "assurance_level": "high"}:
    every listed key must match its expected value in
    context["security_context"] (the reserved sub-key every real
    authorization context carries, see
    context/request_context_builder.py), not the top-level context dict.
    this app does not implement MFA/device-trust
    infrastructure itself: it only checks whatever fields a future trust-
    signal layer populates into that sub-key.

    Fails safe (denies) if context (or its security_context sub-key) is
    missing entirely, or any listed key is absent from it; an unset
    security signal must never be treated as satisfied by default.
    """

    def evaluate(self, condition_value, user_email, resource, context) -> bool:
        if not condition_value:
            return True
        security_context = (context or {}).get("security_context")
        if not security_context:
            return False
        for key, expected_value in condition_value.items():
            if key not in security_context:
                return False
            if security_context.get(key) != expected_value:
                return False
        return True
