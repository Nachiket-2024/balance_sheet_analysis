from dataclasses import dataclass

from .permissions import Permission

# Catalog descriptions are rendered as the primary label in compact two-column
# permission cards. Keep them short enough to remain readable at desktop zoom
# levels; the action key remains available through the copy control.
PERMISSION_DESCRIPTION_MAX_LENGTH = 96


@dataclass(frozen=True)
class PermissionCatalogEntry:
    """One entry in the read-only permission catalog: an action from the
    fixed `Permission` vocabulary, the resource_type it's actually checked
    against (see each action's `require_authorization`/`*_DEPENDENCY` call
    site), and a short operator-facing description of what it grants."""

    action: str
    resource_type: str
    description: str

    def __post_init__(self) -> None:
        if not self.description.strip() or len(self.description) > PERMISSION_DESCRIPTION_MAX_LENGTH:
            raise ValueError(f"Permission descriptions must be 1-{PERMISSION_DESCRIPTION_MAX_LENGTH} characters")


# The resource_type each action is actually checked against, mirroring the
# `require_authorization(action, resource_type)` call sites. A Policy or
# UserPermission only matches a route when its resource_type equals this
# value (or "*"), so this is what makes a grant real rather than dead.
_RESOURCE_TYPE_BY_ACTION: dict[Permission, str] = {
    Permission.USERS_READ_OWN: "users",
    Permission.USERS_UPDATE_OWN: "users",
    Permission.USERS_LIST_ALL: "users",
    Permission.USERS_UPDATE_ANY: "users",
    Permission.USERS_DEACTIVATE_ANY: "users",
    Permission.USERS_ASSIGN_ROLE: "users",
    Permission.USERS_REACTIVATE: "users",
    Permission.USERS_ASSIGN_SYSTEM_ROLE: "users",
    Permission.USERS_DELETE_ANY: "users",
    Permission.POLICIES_READ: "policies",
    Permission.POLICIES_CREATE: "policies",
    Permission.POLICIES_UPDATE: "policies",
    Permission.POLICIES_DELETE: "policies",
    Permission.POLICIES_ASSIGN: "policies",
    Permission.POLICIES_REVOKE: "policies",
    Permission.PERMISSIONS_GRANT: "permissions",
    Permission.PERMISSIONS_REVOKE: "permissions",
    Permission.PERMISSIONS_READ: "permissions",
    Permission.SECURITY_AUDIT_READ: "security_audit",
    Permission.RATE_LIMITS_READ: "rate_limits",
    Permission.RATE_LIMITS_RESET: "rate_limits",
}

_DESCRIPTION_BY_ACTION: dict[Permission, str] = {
    Permission.USERS_READ_OWN: "Read one's own user profile.",
    Permission.USERS_UPDATE_OWN: "Update one's own user profile.",
    Permission.USERS_LIST_ALL: "List and view any user's profile.",
    Permission.USERS_UPDATE_ANY: "Update any user's profile.",
    Permission.USERS_DEACTIVATE_ANY: "Deactivate any user's account. Reversible and auditable.",
    Permission.USERS_ASSIGN_ROLE: "Assign a non-system role to another user.",
    Permission.USERS_REACTIVATE: "Reactivate a soft-deleted/deactivated account.",
    Permission.USERS_ASSIGN_SYSTEM_ROLE: "Assign the system role to another user.",
    Permission.USERS_DELETE_ANY: "Permanently delete any user's account and data.",
    Permission.POLICIES_READ: "Read/list policies.",
    Permission.POLICIES_CREATE: "Create a new policy.",
    Permission.POLICIES_UPDATE: "Edit an existing policy's fields.",
    Permission.POLICIES_DELETE: "Delete a policy.",
    Permission.POLICIES_ASSIGN: "Assign a policy to a user.",
    Permission.POLICIES_REVOKE: "Revoke a policy from a user.",
    Permission.PERMISSIONS_GRANT: "Grant one direct permission to a user, outside a policy.",
    Permission.PERMISSIONS_REVOKE: "Remove a direct permission grant from a user.",
    Permission.PERMISSIONS_READ: "Read direct grants and browse the permission catalog.",
    Permission.SECURITY_AUDIT_READ: "Read security events such as login, logout, and password resets.",
    Permission.RATE_LIMITS_READ: "Read live rate-limit counters.",
    Permission.RATE_LIMITS_RESET: "Manually clear a live rate-limit counter.",
}


PERMISSION_CATALOG: list[PermissionCatalogEntry] = [
    PermissionCatalogEntry(
        action=member.value,
        resource_type=_RESOURCE_TYPE_BY_ACTION[member],
        description=_DESCRIPTION_BY_ACTION[member],
    )
    for member in Permission
]
