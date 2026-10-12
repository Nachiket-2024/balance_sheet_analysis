"""merge refresh-token and app migration heads

Revision ID: a9b0c1d2e3f4
Revises: f5a1c2e8b7d7, f6c7d8e9a0b1
"""
from collections.abc import Sequence

revision: str = "a9b0c1d2e3f4"
down_revision: str | Sequence[str] | None = ("f5a1c2e8b7d7", "f6c7d8e9a0b1")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
