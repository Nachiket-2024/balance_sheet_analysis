# Names of the three policies this template seeds out of the box. The actual
# policy definitions (actions, resource_type, conditions) live only in the
# Alembic migration that creates and seeds the policies/user_policies tables:
# migrations are a historical record and must keep producing the same rows
# regardless of later edits to application-code constants, so the migration
# deliberately keeps its own inline copy rather than importing from here.
#
# These name constants are the reusable part, used to look up and assign the
# already-seeded policies by name:
#   - signup_service, which assigns SELF_SERVICE_POLICY_NAME to every new
#     user ("New users must receive access through default policy
#     assignment, not default roles" : claude.md)
#   - scripts/create_system_user.py, which assigns all three to the new
#     system superuser account
#
# Action identifiers (defined in the migration, not here) match
# authorization/permissions.py's Permission enum values : that enum remains
# the action vocabulary (claude.md: "Permissions represent possible actions
# only"); only the old role -> permission mapping
# (authorization/role_permissions.py) was RBAC and has been removed.

SELF_SERVICE_POLICY_NAME = "self_service"
USER_ADMINISTRATION_POLICY_NAME = "user_administration"
SYSTEM_SUPERUSER_POLICY_NAME = "system_superuser"
