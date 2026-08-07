import enum


class Permission(str, enum.Enum):
    """
    The fixed vocabulary of action identifiers usable in a Policy's
    `actions` list (see authorization/models/policy_model.py) and checked
    via authorization.dependencies.authorization_dependency.require_authorization
    or authorization.services.authorization_service.authorize/require.

    "Permissions represent possible actions only. ...
    Access is granted only when a policy evaluation allows the action."
    This enum is that action vocabulary : nothing more. It carries no
    role -> action mapping (that concept has been removed entirely); the
    only thing that ever grants an action to a user is an assigned,
    active Policy whose `actions` include it (see
    authorization/evaluators/policy_evaluator.py).

    Naming convention: "<resource>:<action>[_<scope>]", e.g.
    USERS_UPDATE_OWN vs USERS_UPDATE_ANY distinguishes "can edit my own
    profile" from "can edit anyone's profile" as genuinely different
    actions, since a policy can plausibly grant one without the other.
    """

    # Self-service: reading/updating one's own profile
    USERS_READ_OWN = "users:read_own"
    USERS_UPDATE_OWN = "users:update_own"

    # User administration: listing/updating/deleting arbitrary accounts
    USERS_LIST_ALL = "users:list_all"
    USERS_UPDATE_ANY = "users:update_any"
    USERS_DELETE_ANY = "users:delete_any"

    # Assigning a role to another user (not system-role assignment, see below)
    USERS_ASSIGN_ROLE = "users:assign_role"

    # Reactivating a soft-deleted/deactivated account : its own action,
    # separate from USERS_UPDATE_ANY, since restoring access is a more
    # sensitive operation than an ordinary profile field edit.
    USERS_REACTIVATE = "users:reactivate"

    # Assigning the system role itself is a separate, more sensitive action
    # from USERS_ASSIGN_ROLE; granting one does not imply the other.
    USERS_ASSIGN_SYSTEM_ROLE = "users:assign_system_role"

    # Permanently, irreversibly removing an account and its rows: a
    # distinct, more sensitive action than USERS_DELETE_ANY (which is a
    # soft delete: reversible, preserves audit history). Hard delete/purge
    # is deliberately gated separately so a policy can grant ordinary user
    # deletion without also granting irreversible data destruction.
    USERS_PURGE = "users:purge"

    # Fine-grained actions for managing the authorization system itself
    # (policies and their assignment to users), see
    # authorization/dependencies/policy_route_dependencies.py. Previously a single coarse
    # "policies:manage" action; split so e.g. a support role could be
    # granted policies:read (to inspect/audit) without also being able to
    # create, edit, delete, or (re)assign policies.
    POLICIES_READ = "policies:read"
    POLICIES_CREATE = "policies:create"
    POLICIES_UPDATE = "policies:update"
    POLICIES_DELETE = "policies:delete"
    POLICIES_ASSIGN = "policies:assign"
    POLICIES_REVOKE = "policies:revoke"

    # Reading the security audit trail (login/logout/signup/OAuth2/password-reset/
    # lockout/token-reuse events : see audit/models/security_audit_log_model.py).
    # Its own action, separate from POLICIES_READ, since it covers a different
    # (non-PBAC) audit surface.
    SECURITY_AUDIT_READ = "security_audit:read"
