from .condition_handler import ConditionHandler
from .condition_types.context_attributes_condition import ContextAttributesCondition
from .condition_types.date_range_condition import DateRangeCondition
from .condition_types.network_condition import NetworkCondition
from .condition_types.resource_attributes_condition import ResourceAttributesCondition
from .condition_types.security_context_condition import SecurityContextCondition
from .condition_types.self_only_condition import SelfOnlyCondition
from .condition_types.time_condition import TimeCondition
from .condition_validator import register_condition_validator


class ConditionRegistry:
    """Maps a condition key (e.g. "self_only", "time") to its handler."""

    def __init__(self) -> None:
        self._handlers: dict[str, ConditionHandler] = {}

    def register(self, key: str, handler: ConditionHandler) -> None:
        self._handlers[key] = handler

    def get(self, key: str) -> ConditionHandler | None:
        return self._handlers.get(key)


# The handlers this template ships with. Downstream applications register
# additional handlers through register_condition_type(), exposed from sdk.py;
# they never edit this upstream-owned module.
default_condition_registry = ConditionRegistry()
default_condition_registry.register("self_only", SelfOnlyCondition())
default_condition_registry.register("resource_attributes", ResourceAttributesCondition())
default_condition_registry.register("context_attributes", ContextAttributesCondition())
default_condition_registry.register("time", TimeCondition())
default_condition_registry.register("date_range", DateRangeCondition())
default_condition_registry.register("network", NetworkCondition())
default_condition_registry.register("security_context", SecurityContextCondition())


def register_condition_type(
    key: str,
    handler: ConditionHandler,
    validator,
) -> None:
    """Add an application-owned condition to the live authorization engine.

    Registration updates both the evaluator registry and write-time
    validation. It must happen during app startup, before requests are served.
    Keys are additive and cannot replace built-ins or another extension.
    """
    if not isinstance(handler, ConditionHandler):
        raise TypeError("handler must be a ConditionHandler")
    register_condition_validator(key, validator)
    default_condition_registry.register(key, handler)
