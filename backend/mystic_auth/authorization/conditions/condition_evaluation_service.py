from .condition_registry import ConditionRegistry, default_condition_registry


class ConditionEvaluationService:
    """
    Sits between PolicyEvaluationEngine and the condition handlers: takes
    a policy's whole `conditions` dict, dispatches each key to its
    registered handler (via ConditionRegistry), and ANDs the results. The
    engine never knows what "self_only" or "time" mean, only that all
    present condition keys must be satisfied.
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
        """`conditions` is a policy's whole conditions block; None/empty
        means an unconditional grant. Thin wrapper over evaluate_detailed
        so there's one evaluation code path, not two."""
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
        key(s) failed instead of just a bool, so PolicyEvaluationEngine
        can build AuthorizationDecision.failed_conditions for a rejected
        policy.

        Every key is checked, not short-circuited, so all failures are
        reported. An unrecognized key (no registered handler) fails safe:
        it counts as failed rather than being ignored.

        Returns {"satisfied": bool, "failed_keys": list[str]}. Denies
        with a single "__invalid_conditions__" key if `conditions` isn't
        a mapping: the JSONB column doesn't enforce shape itself, so this
        is defense in depth against conditions reaching evaluation some
        way other than the validated management API.
        """
        if not conditions:
            return {"satisfied": True, "failed_keys": []}
        if not isinstance(conditions, dict):
            return {"satisfied": False, "failed_keys": ["__invalid_conditions__"]}

        failed_keys: list[str] = []
        for key, value in conditions.items():
            handler = self._registry.get(key)
            if handler is None or not handler.evaluate(value, user_email, resource, context):
                failed_keys.append(key)

        return {"satisfied": len(failed_keys) == 0, "failed_keys": failed_keys}


condition_evaluation_service = ConditionEvaluationService(default_condition_registry)
