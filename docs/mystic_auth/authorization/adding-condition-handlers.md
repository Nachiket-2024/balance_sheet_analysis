# Adding New Condition Handlers
---

*New to a term here? See the [Authorization Glossary](../glossary/authorization.md).*

The condition framework is modular by design:

```mermaid
%%{init: {"themeVariables": {"lineColor": "#334155"}} }%%
flowchart TD
    Engine["Authorization\n Engine\n policy_evaluator.py"]
    Service["Condition\n Evaluation Service\n condition_evaluation_\n service.py"]
    Handlers["Condition\n Handlers\n condition_types/*.py"]
    Engine --> Service --> Handlers
    linkStyle default stroke:#334155,stroke-width:2px
```
---

Downstream projects must keep their condition handlers and validators under
`backend/app/`. Do not edit the registry, validator, evaluator, or any other
file under the upstream-owned `backend/mystic_auth/` tree. The template
provides `register_condition_type()` through `backend/app/sdk.py` and calls
`register_extensions()` from the app-owned `backend/app/app_sdk.py` before
serving requests.

If an existing condition type is sufficient, use it (see [Common
Patterns](common-patterns.md)). If the app genuinely needs a new condition
type, add it entirely in the app tree:

```python
# backend/app/authorization/conditions/project_scope.py
from app.sdk import ConditionHandler


class ProjectScopeCondition(ConditionHandler):
    def evaluate(self, condition_value, user_email, resource, context) -> bool:
        try:
            return (context or {}).get("project_id") == condition_value.get("project_id")
        except Exception:
            return False


def validate_project_scope(value) -> list[str]:
    if not isinstance(value, dict) or not isinstance(value.get("project_id"), str):
        return ["'project_scope.project_id' must be a string"]
    return []
```

Then register it from the app-owned SDK hook:

```python
# backend/app/app_sdk.py
from .authorization.conditions.project_scope import ProjectScopeCondition, validate_project_scope
from .sdk import register_condition_type


def register_extensions() -> None:
    register_condition_type("project_scope", ProjectScopeCondition(), validate_project_scope)
```

`backend/app/main.py` calls `register_extensions()` during startup. The
registration updates both write-time validation and runtime evaluation.
The handler must be synchronous, cheap, and fail closed. The app's route and
policy UI can use the new key without any MysticAuth file changes.

For an upstream MysticAuth feature maintained in this repository, adding a
new condition type **never** requires touching `PolicyEvaluationEngine` or
`ConditionEvaluationService`: add the handler, registry entry, and validator
alongside the corresponding tests. Downstream projects should use the
app-owned registration hook above instead.

---

## 1. Create the handler class (upstream contributors only)

Add a new file beside the other condition implementations, for example `backend/mystic_auth/authorization/conditions/condition_types/device_trust_condition.py`. Do not put condition-specific logic in `condition_registry.py`, `condition_validator.py`, or `condition_evaluation_service.py`; those files are the framework the handlers plug into.

```python
from ..condition_handler import ConditionHandler


class DeviceTrustCondition(ConditionHandler):
    """
    "device_trust": {"min_level": "high"}: the caller's device trust
    level (context["security_context"]["trust_level"]) must meet or
    exceed the required minimum.
    """

    _LEVELS = {"low": 0, "medium": 1, "high": 2}

    def evaluate(self, condition_value, user_email, resource, context) -> bool:
        try:
            required = condition_value.get("min_level")
            security_context = (context or {}).get("security_context") or {}
            actual = security_context.get("trust_level")
            if required not in self._LEVELS or actual not in self._LEVELS:
                return False
            return self._LEVELS[actual] >= self._LEVELS[required]
        except Exception:
            return False
```

**Rules every handler must follow** (see `condition_handler.py`'s `ConditionHandler` ABC docstring):

- Implement `evaluate(self, condition_value, user_email, resource, context) -> bool`.
- **Fail safe.** Malformed condition config, missing required resource/context, or any internal error must result in `False` (deny): wrap risky logic in `try/except`, never let an exception escape past this boundary, and never let an ambiguous case default to `True`.
- Read only what you need from `resource`/`context`: don't reach into the database or make network calls. The engine calls this synchronously and expects it to be cheap.

---

## 2. Register it with the registry (upstream contributors only)

Edit `backend/mystic_auth/authorization/conditions/condition_registry.py`:

```python
from .condition_types.device_trust_condition import DeviceTrustCondition

default_condition_registry.register("device_trust", DeviceTrustCondition())
```

This is the upstream-only wiring point. `ConditionEvaluationService` looks handlers up by key from this registry: it has no other knowledge of what condition types exist. Downstream projects must use the app-owned `register_condition_type()` example above instead.

---

## 3. Add validation (upstream contributors only)

Edit `backend/mystic_auth/authorization/conditions/condition_validator.py`: add both the key and its validator function, so a malformed `device_trust` block is rejected at `POST`/`PUT /authorization/policies` time rather than only failing safe at evaluation time:

```python
def _validate_device_trust(value) -> list[str]:
    if not isinstance(value, dict):
        return ["'device_trust' must be an object"]
    if value.get("min_level") not in ("low", "medium", "high"):
        return ["'device_trust.min_level' must be one of 'low', 'medium', 'high'"]
    return []

_VALIDATORS["device_trust"] = _validate_device_trust
```

Also add `"device_trust"` to `_SUPPORTED_KEYS` in the same file: an unrecognized key is rejected outright, so forgetting this step means every policy using your new condition gets a 422 at creation time.

---

## 4. Test the new condition handler

Three levels, mirroring how every existing condition is tested (see `tests/backend/mystic_auth/unit/authorization/conditions/test_policy_conditions_unit.py` for the pattern on simple handlers like `self_only`/`resource_attributes`/`context_attributes`, or the sibling `test_policy_conditions_temporal_unit.py`/`test_policy_conditions_network_security_unit.py` for handlers with more state, like `time`/`date_range`/`network`/`security_context`):

**Unit test the handler in isolation** (no DB, no evaluator):

```python
def test_device_trust_allows_when_level_meets_minimum():
    handler = DeviceTrustCondition()
    context = {"security_context": {"trust_level": "high"}}
    assert handler.evaluate({"min_level": "medium"}, "u@example.com", None, context) is True

def test_device_trust_fails_safe_on_missing_context():
    handler = DeviceTrustCondition()
    assert handler.evaluate({"min_level": "high"}, "u@example.com", None, None) is False
```

**Unit test the validator** (see `tests/backend/mystic_auth/unit/authorization/conditions/test_condition_validator_unit.py`'s pattern):

```python
def test_device_trust_rejects_invalid_min_level():
    with pytest.raises(ConditionValidationError):
        validate_conditions({"device_trust": {"min_level": "extreme"}})
```

**Add a schema-consistency test** (see `tests/backend/mystic_auth/unit/authorization/conditions/test_condition_schema_consistency_unit.py`) proving the validator and the handler agree on the exact same JSON shape: this is what caught the `date_range` `start`/`end` naming as the one true canonical shape during this project's own condition-schema audit.

**Optionally, a real-DB integration/security test** (see `tests/backend/mystic_auth/security/test_context_spoofing_security.py` for the pattern) proving the condition is enforced end-to-end through a real route, not just the handler in isolation.

---

## What you should never need to change

- `policy_evaluator.py`: it only matches action/resource_type and delegates the whole `conditions` block; it has no per-condition-type logic.
- `condition_evaluation_service.py`: its dispatch loop is generic; it just looks up whatever key is present.
- Any existing condition handler: they're independent of each other.

---
