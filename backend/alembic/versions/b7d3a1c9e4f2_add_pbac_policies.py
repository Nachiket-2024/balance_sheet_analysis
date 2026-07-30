"""add PBAC policies and user_policies tables

Revision ID: b7d3a1c9e4f2
Revises: f2754349a6c7
Create Date: 2026-07-13 00:00:00.000000

Introduces the real Policy-Based Access Control (PBAC) schema per
claude.md's target architecture, replacing the role -> permission mapping
that previously lived in application code (authorization/role_permissions.py,
now removed):

  - policies: the primary authorization unit (identity, description,
    granted actions, resource type, optional conditions, audit fields).
  - user_policies: the many-to-many assignment of policies to users — the
    ONLY thing that determines what a user can do.

This migration also seeds the three baseline policies the application ships
with (authorization/policies/default_policies.py) and — as a one-time
bridge — assigns each *existing* user the policy set that reproduces their
current role's access exactly, so upgrading doesn't change anyone's
effective permissions. This is a data migration reading the old `role`
column, not an ongoing dependency on it: from this point forward, role is
metadata only, and authorization reads user_policies/policies exclusively.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b7d3a1c9e4f2'
down_revision: str | Sequence[str] | None = 'f2754349a6c7'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# ---------------------------- Baseline Policy Definitions ----------------------------
# Mirrors authorization/policies/default_policies.py. Duplicated here
# (rather than imported) deliberately: a migration must keep producing the
# exact same schema/data years from now even if the application-code
# constants are later edited — migrations are a historical record, not a
# live view of current application state.
_SELF_SERVICE = {
    "name": "self_service",
    "description": "Baseline access every account gets: read and update one's own user profile.",
    "actions": ["users:read_own", "users:update_own"],
    "resource_type": "users",
}
_USER_ADMINISTRATION = {
    "name": "user_administration",
    "description": "Manage other users' accounts: list, update, delete, assign non-system roles.",
    "actions": ["users:list_all", "users:update_any", "users:delete_any", "users:assign_role"],
    "resource_type": "users",
}
_SYSTEM_SUPERUSER = {
    "name": "system_superuser",
    "description": (
        "The most sensitive actions: assigning the system role, promoting to "
        "admin, and managing the authorization system itself."
    ),
    "actions": ["users:assign_system_role", "users:promote_to_admin", "policies:manage"],
    # "*": spans two resource types (users, policies) — see
    # authorization/policies/default_policies.py for the full rationale.
    "resource_type": "*",
}


def upgrade() -> None:
    # ---------------------------- Create policies table ----------------------------
    op.create_table(
        'policies',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.String(), nullable=True),
        sa.Column('actions', postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column('resource_type', sa.String(), nullable=False),
        sa.Column('conditions', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by', sa.String(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_policies_id'), 'policies', ['id'], unique=False)
    op.create_index(op.f('ix_policies_name'), 'policies', ['name'], unique=True)

    # ---------------------------- Create user_policies table ----------------------------
    op.create_table(
        'user_policies',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('policy_id', sa.Integer(), nullable=False),
        sa.Column('assigned_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('assigned_by', sa.String(), nullable=True),
        sa.ForeignKeyConstraint(['policy_id'], ['policies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'policy_id', name='uq_user_policy'),
    )
    op.create_index(op.f('ix_user_policies_id'), 'user_policies', ['id'], unique=False)
    op.create_index(op.f('ix_user_policies_policy_id'), 'user_policies', ['policy_id'], unique=False)
    op.create_index(op.f('ix_user_policies_user_id'), 'user_policies', ['user_id'], unique=False)

    # ---------------------------- Seed baseline policies ----------------------------
    connection = op.get_bind()

    policies_table = sa.table(
        'policies',
        sa.column('id', sa.Integer),
        sa.column('name', sa.String),
        sa.column('description', sa.String),
        sa.column('actions', postgresql.ARRAY(sa.String())),
        sa.column('resource_type', sa.String),
        sa.column('is_active', sa.Boolean),
        sa.column('created_by', sa.String),
    )

    seeded_policy_ids: dict[str, int] = {}
    for policy in (_SELF_SERVICE, _USER_ADMINISTRATION, _SYSTEM_SUPERUSER):
        result = connection.execute(
            policies_table.insert().values(
                name=policy["name"],
                description=policy["description"],
                actions=policy["actions"],
                resource_type=policy["resource_type"],
                is_active=True,
                created_by="system",
            ).returning(policies_table.c.id)
        )
        seeded_policy_ids[policy["name"]] = result.scalar_one()

    # ---------------------------- Bridge existing users: role -> policy assignment ----------------------------
    # One-time data migration so upgrading never changes anyone's effective
    # access: every existing user gets self_service; admin/system also get
    # user_administration; system also gets system_superuser. From here on,
    # the `role` column is never read to make this decision again.
    users_table = sa.table(
        'users',
        sa.column('id', sa.Integer),
        sa.column('role', sa.String),
    )
    user_policies_table = sa.table(
        'user_policies',
        sa.column('user_id', sa.Integer),
        sa.column('policy_id', sa.Integer),
        sa.column('assigned_by', sa.String),
    )

    existing_users = connection.execute(sa.select(users_table.c.id, users_table.c.role)).fetchall()

    assignments = []
    for user_id, role in existing_users:
        policy_names_for_role = ["self_service"]
        if role in ("admin", "system"):
            policy_names_for_role.append("user_administration")
        if role == "system":
            policy_names_for_role.append("system_superuser")

        for policy_name in policy_names_for_role:
            assignments.append({
                "user_id": user_id,
                "policy_id": seeded_policy_ids[policy_name],
                "assigned_by": "system_migration",
            })

    if assignments:
        connection.execute(user_policies_table.insert(), assignments)


def downgrade() -> None:
    op.drop_index(op.f('ix_user_policies_user_id'), table_name='user_policies')
    op.drop_index(op.f('ix_user_policies_policy_id'), table_name='user_policies')
    op.drop_index(op.f('ix_user_policies_id'), table_name='user_policies')
    op.drop_table('user_policies')

    op.drop_index(op.f('ix_policies_name'), table_name='policies')
    op.drop_index(op.f('ix_policies_id'), table_name='policies')
    op.drop_table('policies')
