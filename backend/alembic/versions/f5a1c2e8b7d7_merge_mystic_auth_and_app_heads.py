"""Merge the MysticAuth and app migration heads after the upstream sync.

Revision ID: f5a1c2e8b7d7
Revises: b0c1d2e3f4a5, f4a1c2e8b7d6
"""

from collections.abc import Sequence

revision: str = "f5a1c2e8b7d7"
down_revision: str | Sequence[str] | None = ("b0c1d2e3f4a5", "f4a1c2e8b7d6")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
