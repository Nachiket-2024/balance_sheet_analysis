"""add five scoped policies

Revision ID: e0291417b733
Revises: e7a2c4d8f1b3
Create Date: 2026-08-22 00:00:00.000000

Seeds five additional, non-protected policies alongside the three original
baseline ones (self_service, user_management, system_superuser), each
scoped to exactly one resource_type so every action in it actually takes
effect (see policy_evaluator.py: a policy only matches when
resource_type == its own resource_type, or "*"):

  - policy_management (resource_type "policies"): full policy-system
    management - read/create/update/delete/assign/revoke.
  - policy_maintainer (resource_type "policies"): a narrower slice of the
    above - read/update/revoke only, for fixing or locking down an
    existing policy without being able to author new ones or reassign
    who's exempt from a delete/revoke escalation guard.
  - rate_limit_management (resource_type "rate_limits"): read/reset.
  - security_audit_access (resource_type "security_audit"): read.
  - user_lifecycle (resource_type "users"): purge/reactivate.

These were originally created ad hoc through the management API (POST
/authorization/policies), which is normally sufficient for a genuinely
custom, one-off policy (see docs/mystic_auth/authorization/
adding-permissions.md's "brand-new policy" guidance) - but a policy that
only exists as a database row doesn't survive a fresh volume/environment
the way the three migration-seeded baseline policies do. Promoted to a
migration so they're always present after `alembic upgrade head`, same as
the original three - not because they're privileged/protected
(PROTECTED_POLICY_NAMES in policy_route_dependencies.py deliberately does
NOT include these five: they stay a normal, editable/deletable policy,
unlike the three true baseline ones the system depends on to function at
all).
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'e0291417b733'
down_revision: str | Sequence[str] | None = 'e7a2c4d8f1b3'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_POLICIES = [
    {
        "name": "policy_management",
        "description": (
            "Manage the policy system itself and grant/revoke policies on other users: "
            "list/create/edit/delete policy definitions, and assign or revoke them."
        ),
        "actions": [
            "policies:read", "policies:create", "policies:update",
            "policies:delete", "policies:assign", "policies:revoke",
        ],
        "resource_type": "policies",
    },
    {
        "name": "policy_maintainer",
        "description": (
            "Fix or lock down existing policies and their assignments (view, edit, revoke) "
            "without being able to create new policies, delete them, or assign new grants."
        ),
        "actions": ["policies:read", "policies:update", "policies:revoke"],
        "resource_type": "policies",
    },
    {
        "name": "rate_limit_management",
        "description": "View and reset rate-limit entries.",
        "actions": ["rate_limits:read", "rate_limits:reset"],
        "resource_type": "rate_limits",
    },
    {
        "name": "security_audit_access",
        "description": "View the security audit log and dashboard login-trend data.",
        "actions": ["security_audit:read"],
        "resource_type": "security_audit",
    },
    {
        "name": "user_lifecycle",
        "description": "Hard-purge a deleted user, or reactivate a deactivated one.",
        "actions": ["users:purge", "users:reactivate"],
        "resource_type": "users",
    },
]


def _policies_table():
    return sa.table(
        'policies',
        sa.column('name', sa.String),
        sa.column('description', sa.String),
        sa.column('actions', postgresql.ARRAY(sa.String())),
        sa.column('resource_type', sa.String),
        sa.column('is_active', sa.Boolean),
        sa.column('created_by', sa.String),
    )


def upgrade() -> None:
    connection = op.get_bind()
    policies_table = _policies_table()
    for policy in _POLICIES:
        connection.execute(
            policies_table.insert().values(
                name=policy["name"],
                description=policy["description"],
                actions=policy["actions"],
                resource_type=policy["resource_type"],
                is_active=True,
                created_by="system",
            )
        )


def downgrade() -> None:
    connection = op.get_bind()
    policies_table = _policies_table()
    connection.execute(
        policies_table.delete().where(
            policies_table.c.name.in_([policy["name"] for policy in _POLICIES])
        )
    )
