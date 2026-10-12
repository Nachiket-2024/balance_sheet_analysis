from fastapi import Depends

from ..permissions import Permission
from .authorization_dependency import require_any_authorization, require_authorization

# Per-operation dependencies for direct-permission-grant routes, mirroring
# policy_route_dependencies.py's shape. "permissions" is the resource_type
# these gate, distinct from "policies".
GRANT_DEPENDENCY = Depends(require_authorization(Permission.PERMISSIONS_GRANT.value, "permissions"))
REVOKE_DEPENDENCY = Depends(require_authorization(Permission.PERMISSIONS_REVOKE.value, "permissions"))
READ_DEPENDENCY = Depends(require_authorization(Permission.PERMISSIONS_READ.value, "permissions"))

# GET /permissions/catalog is a prerequisite of several unrelated features
# (Policy form's actions multi-select, permission-grant dialogs), none of
# which should also require permissions:read on their own. Without this, a
# caller granted only e.g. permissions:grant could open the grant dialog but
# its dropdown would always fail to load.
CATALOG_READ_DEPENDENCY = Depends(
    require_any_authorization(
        [
            (Permission.PERMISSIONS_READ.value, "permissions"),
            (Permission.POLICIES_CREATE.value, "policies"),
            (Permission.POLICIES_UPDATE.value, "policies"),
            (Permission.PERMISSIONS_GRANT.value, "permissions"),
        ]
    )
)
