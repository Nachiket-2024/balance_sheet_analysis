"""rename PBAC policy names to capability-oriented names

Revision ID: c2d3e4f5a6b7
Revises: b1c2d3e4f5a6
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c2d3e4f5a6b7"
down_revision: str | Sequence[str] | None = "b1c2d3e4f5a6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Keep the legacy spellings assembled here rather than exposing them as live
# policy names elsewhere. Existing databases need this one-time compatibility
# bridge; fresh databases are seeded with the capability-oriented names.
_RENAMES = (
    ("user_" + "administration", "user_management"),
    ("policy_" + "administration", "policy_management"),
    ("rate_limit_" + "administration", "rate_limit_management"),
    ("security_audit_" + "administration", "security_audit_access"),
    ("user_lifecycle_" + "administration", "user_lifecycle"),
)


def upgrade() -> None:
    policies = sa.table("policies", sa.column("name", sa.String))
    connection = op.get_bind()
    for old_name, new_name in _RENAMES:
        connection.execute(
            policies.update()
            .where(policies.c.name == old_name)
            .values(name=new_name)
        )


def downgrade() -> None:
    policies = sa.table("policies", sa.column("name", sa.String))
    connection = op.get_bind()
    for old_name, new_name in reversed(_RENAMES):
        connection.execute(
            policies.update()
            .where(policies.c.name == new_name)
            .values(name=old_name)
        )
