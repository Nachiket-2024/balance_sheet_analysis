from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ....authorization.dependencies.permission_route_dependencies import CATALOG_READ_DEPENDENCY, READ_DEPENDENCY
from ....authorization.permissions_catalog import PERMISSION_CATALOG
from ....authorization.repositories.permission_usage_repository import permission_usage_repository
from ....authorization.schemas.permission_schema import PermissionCatalogEntryRead, PermissionUsageEntryRead
from ....database.connection import database

router = APIRouter(prefix="/authorization", tags=["Authorization"])


@router.get("/permissions/catalog", response_model=list[PermissionCatalogEntryRead])
async def get_permission_catalog(current_user: dict = CATALOG_READ_DEPENDENCY):
    """The built-in, code-defined action reference an authorized operator can assign, either
    directly or bundled into a Policy (see authorization/permissions_catalog.py).
    Downstream application actions are opaque strings and are managed by the
    application's own catalog or authorization UI.
    Static and small (~20 entries), so no pagination/filter/sort: the
    frontend does that client-side.

    Gated by CATALOG_READ_DEPENDENCY (permissions:read OR policies:create OR
    policies:update), not permissions:read alone, since the Policy
    create/edit form needs this catalog too - see that dependency's
    docstring."""
    return PERMISSION_CATALOG


@router.get("/permissions/catalog/usage", response_model=list[PermissionUsageEntryRead])
async def get_permission_catalog_usage(
    current_user: dict = READ_DEPENDENCY,
    db: AsyncSession = Depends(database.get_session),
):
    """Who actually holds each catalog action right now (see
    PermissionUsageRepository.get_usage_by_action): which active policies
    grant it and how many users each reaches, how many users hold it as a
    direct grant, and the deduplicated total. Backs the Permissions page's
    "Held by" column, its Unused/In-a-policy/Direct-grants quick filters,
    and the details dialog.

    Gated by permissions:read alone, unlike the catalog itself
    (CATALOG_READ_DEPENDENCY): this discloses who holds what, which the
    Policy/permission-grant forms that share the catalog's own broader
    gate don't need."""
    usage_by_action = await permission_usage_repository.get_usage_by_action(db)
    return [usage_by_action[entry.action] for entry in PERMISSION_CATALOG]
