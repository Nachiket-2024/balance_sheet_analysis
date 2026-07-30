from .condition_registry import ConditionRegistry, default_condition_registry


class ConditionEvaluationService:
    """
    Sits between the authorization engine (PolicyEvaluationEngine) and the
    individual condition handlers:

        Authorization Engine -> Condition Evaluation Service -> Condition Handlers

    The engine calls this service with a policy's whole `conditions` dict;
    this service dispatches each key to its registered handler (via
    ConditionRegistry) and ANDs the results. The engine itself never knows
    what "self_only" or "time" mean, only that "all present condition
    keys must be satisfied".
    """

    def __init__(self, registry: ConditionRegistry) -> None:
        self._registry = registry

    def evaluate(
        self,
        conditions: dict | None,
        user_email: str,
        resource: dict | object | None,
        context: dict | None,
    ) -> bool:
        """
        `conditions` is a policy's whole conditions block, e.g.
        {"self_only": True, "time": {...}}; None/empty means an
        unconditional grant. Thin wrapper over evaluate_detailed (mirrors
        PolicyEvaluationEngine.evaluate's relationship to its own
        evaluate_detailed): one evaluation code path, not two.
        """
        return self.evaluate_detailed(conditions, user_email, resource, context)["satisfied"]

    def evaluate_detailed(
        self,
        conditions: dict | None,
        user_email: str,
        resource: dict | object | None,
        context: dict | None,
    ) -> dict:
        """
        Same inputs as evaluate(), but reports exactly which condition
        key(s) failed rather than just a bool: this is what lets
        PolicyEvaluationEngine build an AuthorizationDecision's
        failed_conditions for a rejected policy, instead of only knowing
        *that* a policy's conditions didn't pass.

        Every key is checked (not short-circuited on the first failure) so
        every failing key is reported. An unrecognized key (no registered
        handler, e.g. a typo, or an unsupported condition type) fails
        safe: it counts as a failed key rather than being silently
        ignored.

        Returns {"satisfied": bool, "failed_keys": list[str]}.
        """
        if not conditions:
            return {"satisfied": True, "failed_keys": []}

        failed_keys: list[str] = []
        for key, value in conditions.items():
            handler = self._registry.get(key)
            if handler is None or not handler.evaluate(value, user_email, resource, context):
                failed_keys.append(key)

        return {"satisfied": len(failed_keys) == 0, "failed_keys": failed_keys}


condition_evaluation_service = ConditionEvaluationService(default_condition_registry)
