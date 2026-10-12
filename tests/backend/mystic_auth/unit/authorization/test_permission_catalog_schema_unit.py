import pytest
from pydantic import ValidationError

from backend.mystic_auth.authorization.permissions_catalog import (
    PERMISSION_DESCRIPTION_MAX_LENGTH,
    PermissionCatalogEntry,
)
from backend.mystic_auth.authorization.schemas.permission_schema import (
    PermissionCatalogEntryRead,
)


def test_permission_catalog_description_has_a_shared_production_limit():
    description = "x" * PERMISSION_DESCRIPTION_MAX_LENGTH

    assert PermissionCatalogEntryRead(action="users:list_all", resource_type="users", description=description).description == description
    PermissionCatalogEntry(action="users:list_all", resource_type="users", description=description)


@pytest.mark.parametrize("description", ["", "x" * (PERMISSION_DESCRIPTION_MAX_LENGTH + 1)])
def test_permission_catalog_description_rejects_empty_or_overlong_values(description):
    with pytest.raises((ValidationError, ValueError)):
        PermissionCatalogEntryRead(action="users:list_all", resource_type="users", description=description)
    with pytest.raises(ValueError):
        PermissionCatalogEntry(action="users:list_all", resource_type="users", description=description)
