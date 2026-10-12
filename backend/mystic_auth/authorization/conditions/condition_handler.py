from abc import ABC, abstractmethod


class ConditionHandler(ABC):
    """One condition type's evaluation logic (e.g. "self_only", "time",
    "network"). ConditionEvaluationService dispatches to whichever handler
    is registered for a condition key via ConditionRegistry, so adding a
    condition type never means touching the evaluator itself.

    Every handler must fail safe: malformed config, missing context/
    resource, or any internal error must make `evaluate` return False,
    never raise or silently allow.
    """

    @abstractmethod
    def evaluate(
        self,
        condition_value,
        user_email: str,
        resource: dict | object | None,
        context: dict | None,
    ) -> bool:
        """`condition_value` is this condition key's value from the
        policy's `conditions` dict. Returns True if satisfied, False
        otherwise (including on error, see class docstring)."""
        raise NotImplementedError
