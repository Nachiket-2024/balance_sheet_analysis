def get_field(obj: dict | object, field: str):
    """
    Reads `field` from a resource, which callers may represent either as a
    plain dict (e.g. ORM-independent test data) or as an attribute-bearing
    object (e.g. a SQLAlchemy model instance). Returns None if the field
    doesn't exist on obj.

    Shared by every condition handler that needs to read a resource field
    (self_only, resource_attributes), so the dict-vs-object duck typing is
    implemented identically everywhere rather than each handler
    reimplementing the same isinstance check.
    """
    return obj.get(field) if isinstance(obj, dict) else getattr(obj, field, None)
