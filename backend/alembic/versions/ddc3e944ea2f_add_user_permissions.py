"""add user_permissions

Revision ID: ddc3e944ea2f
Revises: e0291417b733
Create Date: 2026-08-27 00:00:00.000000

Adds the user_permissions table: a direct, per-user grant of a single
action (bypassing Policy entirely), the granular counterpart to
UserPolicy/policies (see authorization/models/user_permission_model.py's
own docstring for why this exists alongside, not instead of, policies).

No data seeding: this table starts empty. Nothing existing depends on it.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "ddc3e944ea2f"
down_revision: str | None = "e0291417b733"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user_permissions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("resource_type", sa.String(), nullable=False),
        sa.Column("conditions", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("assigned_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("assigned_by", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "action", "resource_type", name="uq_user_permission"),
    )
    op.create_index(op.f("ix_user_permissions_id"), "user_permissions", ["id"], unique=False)
    op.create_index(op.f("ix_user_permissions_user_id"), "user_permissions", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_user_permissions_user_id"), table_name="user_permissions")
    op.drop_index(op.f("ix_user_permissions_id"), table_name="user_permissions")
    op.drop_table("user_permissions")
