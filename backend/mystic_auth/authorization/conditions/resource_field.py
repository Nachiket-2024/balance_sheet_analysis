from typing import Any


def get_field(obj: dict | object, field: str) -> Any:
    """Reads `field` from a resource, whether it's a dict (test data) or an
    object (e.g. ORM model). Shared so every condition handler duck-types
    the same way instead of reimplementing the isinstance check."""
    return obj.get(field) if isinstance(obj, dict) else getattr(obj, field, None)
