"""Merge the latest MysticAuth and app migration heads.

Revision ID: b0c1d2e3f4a5
Revises: a7b8c9d0e1f2, a8c5d7e9f1b3
"""

from collections.abc import Sequence

revision: str = "b0c1d2e3f4a5"
down_revision: str | Sequence[str] | None = ("a7b8c9d0e1f2", "a8c5d7e9f1b3")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
