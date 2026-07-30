from .condition_handler import ConditionHandler


class ContextAttributesCondition(ConditionHandler):
    """
    "context_attributes": {key: expected_value, ...}: every listed key
    must match its expected value in the caller-supplied context (e.g.
    {"mfa_verified": True} for an MFA-gated action). An empty/missing map
    imposes no restriction. Unsatisfiable if no context was supplied.
    """

    def evaluate(self, condition_value, user_email, resource, context) -> bool:
        if not condition_value:
            return True
        if context is None:
            return False
        return all(context.get(key) == expected_value for key, expected_value in condition_value.items())
