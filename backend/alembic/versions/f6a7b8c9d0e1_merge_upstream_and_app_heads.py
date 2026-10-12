"""Merge upstream and app migration branches.

Revision ID: f6a7b8c9d0e1
Revises: 2056f1b0bfeb, c2d3e4f5a6b7
Create Date: 2026-09-29
"""

from collections.abc import Sequence

revision: str = "f6a7b8c9d0e1"
down_revision: str | Sequence[str] | None = ("2056f1b0bfeb", "c2d3e4f5a6b7")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
