import enum


class Permission(str, enum.Enum):
    """
    MysticAuth's built-in vocabulary of action identifiers usable in a
    Policy's `actions` list, checked via require_authorization or
    AuthorizationService.authorize/require. Downstream applications may use
    additional opaque action strings without adding them here.

    Represents possible actions only, no role -> action mapping: the only
    thing that grants an action to a user is an assigned, active Policy
    whose `actions` include it (see evaluators/policy_evaluator.py).

    Naming convention: "<resource>:<action>[_<scope>]", e.g.
    USERS_UPDATE_OWN vs USERS_UPDATE_ANY are genuinely different actions
    since a policy can grant one without the other.
    """

    # Self-service: reading/updating one's own profile
    USERS_READ_OWN = "users:read_own"
    USERS_UPDATE_OWN = "users:update_own"

    # User management: listing/updating/deleting arbitrary accounts
    USERS_LIST_ALL = "users:list_all"
    USERS_UPDATE_ANY = "users:update_any"

    # Soft-delete (deactivate): reversible, preserves audit history. Named
    # to match its UI label ("Deactivate") exactly - see USERS_DELETE_ANY
    # below for the distinct, irreversible action that label pair maps to.
    USERS_DEACTIVATE_ANY = "users:deactivate_any"

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
    # distinct, more sensitive action than USERS_DEACTIVATE_ANY (which is a
    # soft delete: reversible, preserves audit history). Named to match its
    # UI label ("Delete") exactly, and gated as its own action - deliberately
    # separate from USERS_DEACTIVATE_ANY - so a policy can grant ordinary
    # deactivation without also granting irreversible data destruction.
    USERS_DELETE_ANY = "users:delete_any"

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

    # Direct, single-action grants to a user (UserPermission), bypassing
    # Policy entirely - see authorization/models/user_permission_model.py.
    # Their own action tier, separate from POLICIES_ASSIGN/REVOKE: granting
    # a bare action directly is more sensitive than assigning a pre-vetted
    # named policy (no policy author reviewed this specific action+
    # conditions combination as a unit), so it gets its own audit-visible
    # permission rather than silently piggybacking on policies:assign.
    PERMISSIONS_GRANT = "permissions:grant"
    PERMISSIONS_REVOKE = "permissions:revoke"
    PERMISSIONS_READ = "permissions:read"

    # Reading the security audit trail (login/logout/signup/OAuth2/password-reset/
    # lockout/token-reuse events: see backend/mystic_auth/audit_log/audit_log_model.py).
    # Its own action, separate from POLICIES_READ, since it covers a different
    # (non-PBAC) audit surface.
    SECURITY_AUDIT_READ = "security_audit:read"

    # Reading live Valkey-backed rate-limit counters (see
    # auth/security/rate_limiting/rate_limiter_service.py). Its own action, separate from
    # SECURITY_AUDIT_READ, since this is live operational state, not a
    # historical log.
    RATE_LIMITS_READ = "rate_limits:read"

    # Manually clearing a live rate-limit counter (DELETE /rate-limits/{key}).
    # Split from RATE_LIMITS_READ so a policy scoped to "can view the
    # dashboard" doesn't also imply "can clear anyone's counters" - the same
    # read/write split every other resource in this enum already gets
    # (policies:read vs policies:create/update/delete, users:list_all vs
    # users:update_any/delete_any). See docs/mystic_auth/concerns/README.md's
    # former "rate_limits:read also grants clearing counters" entry.
    RATE_LIMITS_RESET = "rate_limits:reset"
