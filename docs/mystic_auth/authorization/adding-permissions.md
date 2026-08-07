# Adding New Permissions

## Where to define a new action

Add it to the `Permission` enum in `backend/mystic_auth/authorization/permissions.py`:

```python
class Permission(str, enum.Enum):
    ...
    PROJECTS_CREATE = "projects:create"
```

Naming convention: `"<resource>:<action>[_<scope>]"`: e.g. `USERS_UPDATE_OWN` vs `USERS_UPDATE_ANY` are genuinely different actions (a policy can grant one without the other), not one action with a role check bolted on.

**`Permission` is a vocabulary, not a grant.** Adding an enum member here does not give anyone access to anything: it only makes the identifier available for a policy's `actions` list. The only thing that ever grants an action is an assigned, active `Policy` whose `actions` include it.

### A note on scope

Every member of `Permission` is treated as one of this app's own **known-sensitive actions**: see `AuthorizationService.assert_authorized_to_grant`'s `_KNOWN_SENSITIVE_ACTIONS` set, which is derived directly from this enum. Adding a permission here means:

- It's subject to the privilege-escalation guard: a caller can never create/update/assign a policy granting this action unless they already hold it themselves.
- It's meant for **this application's own identity/authorization concerns** (user management, policy management). A downstream project's own business-domain actions (e.g. `"documents:view"`, `"projects:create"`) do **not** need to go in this enum at all: policies can grant arbitrary action strings freely, and only strings actually listed in `Permission` are escalation-guarded. Only add an enum member here if the action is sensitive enough that you want that guard to apply.

---

## How to update seed policies

The three baseline policies (`self_service`, `user_administration`, `system_superuser`) are seeded by Alembic migrations, **not** read from application code at migration time:

- `backend/alembic/versions/b7d3a1c9e4f2_add_pbac_policies.py`: the original seed.
- `backend/alembic/versions/e2b6c8a4f1d5_split_policies_manage_action.py`: an example of a later **data-only migration** that updated one seeded policy's `actions` array in place.

This is deliberate: migrations are a historical record and must keep producing the same rows years from now even if `permissions.py`'s constants are later renamed or removed. `authorization/policies/default_policies.py` only holds the three policy **name** constants (`SELF_SERVICE_POLICY_NAME`, etc.): used to look up and assign already-seeded policies: never the actual action lists.

**To grant a new permission to an existing baseline policy**, write a new data-only migration (do not edit the old seed migration):

```python
"""add projects:create to user_administration"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

def upgrade() -> None:
    connection = op.get_bind()
    policies_table = sa.table(
        'policies',
        sa.column('name', sa.String),
        sa.column('actions', postgresql.ARRAY(sa.String())),
    )
    connection.execute(
        policies_table.update()
        .where(policies_table.c.name == 'user_administration')
        .values(actions=['users:list_all', 'users:update_any', 'users:delete_any', 'users:assign_role', 'projects:create'])
    )

def downgrade() -> None:
    # revert to the previous actions list
    ...
```

**To add a brand-new (non-baseline) policy**, just use the management API (`POST /authorization/policies`, requires `policies:create`: see [Policy JSON Examples](policy-examples.md)): no migration needed. Only the three seeded baseline policies live in migrations.

---

## Migration considerations

- Never edit an already-applied migration's seed data in place: write a new migration.
- A migration that changes a seeded policy's `actions` should also update `downgrade()` symmetrically (restore the previous array) so the migration is safely reversible.
- If you rename or remove a `Permission` enum member that's referenced by a seeded policy, the seeded row's `actions` array (a plain string array in the database, not a foreign key to the enum) is completely unaffected: but update it via a new migration if the old action string should no longer be granted.
- Test new fine-grained actions the same way the existing `policies:read/create/update/delete/assign/revoke` split was tested: real-API integration tests proving a caller holding *only* the new action can do the one thing it should, and nothing else (see `tests/backend/mystic_auth/integration/authorization/test_policy_action_separation_integration.py`'s `_attempt_policy_routes` pattern).

---

## Roles vs. policies

Roles (`users.role`) are **display/grouping metadata only**: nullable, never read by the authorization service, evaluator, or condition handlers. New users (signup and OAuth2) receive access purely through an explicit `self_service` policy assignment (`authorization_repository.assign_policy_to_user`), never through a default role. If you're tempted to add a role-based shortcut anywhere in the authorization path, don't: see `authorization/services/authorization_service.py`'s own docstring for why.
