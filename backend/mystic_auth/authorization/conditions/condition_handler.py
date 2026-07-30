from abc import ABC, abstractmethod


class ConditionHandler(ABC):
    """
    One condition type's evaluation logic (e.g. "self_only", "time",
    "network"). The ConditionEvaluationService dispatches to whichever
    handler is registered for a given condition key via
    ConditionRegistry: the evaluator (PolicyEvaluationEngine) never
    contains condition-specific logic itself, so adding a new condition
    type never requires touching the evaluator or the service, only
    registering a new handler (see conditions/condition_registry.py).

    Every handler must fail safe: malformed condition config, missing
    required context/resource, or any internal error must result in
    `evaluate` returning False (deny), never raising past this boundary
    and never silently allowing.
    """

    @abstractmethod
    def evaluate(
        self,
        condition_value,
        user_email: str,
        resource: dict | object | None,
        context: dict | None,
    ) -> bool:
        """
        `condition_value` is this condition key's value from the policy's
        `conditions` dict (e.g. {"start": "09:00", ...} for a "time"
        condition, or a plain bool for "self_only"). Returns True if this
        condition is satisfied, False otherwise (including on any error,
        see class docstring).
        """
        raise NotImplementedError
