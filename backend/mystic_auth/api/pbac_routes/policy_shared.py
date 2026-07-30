from fastapi import Depends

from ...authorization.dependencies.authorization_dependency import require_authorization
from ...authorization.permissions import Permission
from ...authorization.policies.default_policies import (
    SELF_SERVICE_POLICY_NAME,
    SYSTEM_SUPERUSER_POLICY_NAME,
    USER_ADMINISTRATION_POLICY_NAME,
)

# Fine-grained per-operation dependencies (replaces the old single coarse
# "policies:manage" action, see permissions.py). A caller can now hold,
# say, policies:read without also being able to create/edit/delete/assign
# policies, and vice versa. Shared across every pbac_routes module below so
# each operation is gated identically no matter which file defines the route.
READ_DEPENDENCY = Depends(require_authorization(Permission.POLICIES_READ.value, "policies"))
CREATE_DEPENDENCY = Depends(require_authorization(Permission.POLICIES_CREATE.value, "policies"))
UPDATE_DEPENDENCY = Depends(require_authorization(Permission.POLICIES_UPDATE.value, "policies"))
DELETE_DEPENDENCY = Depends(require_authorization(Permission.POLICIES_DELETE.value, "policies"))
ASSIGN_DEPENDENCY = Depends(require_authorization(Permission.POLICIES_ASSIGN.value, "policies"))
REVOKE_DEPENDENCY = Depends(require_authorization(Permission.POLICIES_REVOKE.value, "policies"))

# Baseline policies the system depends on to keep functioning: never
# deletable, renameable, or deactivatable via the generic management API
# (see policy_crud_routes.py), regardless of who holds policies:delete or
# policies:update.
PROTECTED_POLICY_NAMES = frozenset(
    {SELF_SERVICE_POLICY_NAME, USER_ADMINISTRATION_POLICY_NAME, SYSTEM_SUPERUSER_POLICY_NAME}
)
