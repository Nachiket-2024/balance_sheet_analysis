from .condition_handler import ConditionHandler
from .context_attributes_condition import ContextAttributesCondition
from .date_range_condition import DateRangeCondition
from .network_condition import NetworkCondition
from .resource_attributes_condition import ResourceAttributesCondition
from .security_context_condition import SecurityContextCondition
from .self_only_condition import SelfOnlyCondition
from .time_condition import TimeCondition


class ConditionRegistry:
    """
    Maps a condition key (as it appears in a Policy's `conditions` dict,
    e.g. "self_only", "time") to the ConditionHandler responsible for it.
    This is the one place that needs to change to add a new condition
    type: neither PolicyEvaluationEngine nor ConditionEvaluationService
    need any change (see conditions/condition_handler.py's docstring).
    """

    def __init__(self) -> None:
        self._handlers: dict[str, ConditionHandler] = {}

    def register(self, key: str, handler: ConditionHandler) -> None:
        self._handlers[key] = handler

    def get(self, key: str) -> ConditionHandler | None:
        return self._handlers.get(key)


# The handlers this app ships with. A downstream application extending this
# template with its own condition types registers additional handlers here
# (or on its own ConditionRegistry instance) without touching anything else
# in the authorization module.
default_condition_registry = ConditionRegistry()
default_condition_registry.register("self_only", SelfOnlyCondition())
default_condition_registry.register("resource_attributes", ResourceAttributesCondition())
default_condition_registry.register("context_attributes", ContextAttributesCondition())
default_condition_registry.register("time", TimeCondition())
default_condition_registry.register("date_range", DateRangeCondition())
default_condition_registry.register("network", NetworkCondition())
default_condition_registry.register("security_context", SecurityContextCondition())
