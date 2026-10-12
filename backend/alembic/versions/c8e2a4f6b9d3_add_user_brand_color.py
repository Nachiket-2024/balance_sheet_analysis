"""add brand_color to users

Revision ID: c8e2a4f6b9d3
Revises: b1e6a9f3c7d2
Create Date: 2026-08-21 00:00:00.000000

Adds a nullable per-user brand color override (#rrggbb), so a signed-in user
can re-skin the app's brand accent/logo/favicon for themselves without
touching the app-wide default in frontend/src/app/theme.ts. NULL means "use
the app default", never a stored literal default, so a fleet-wide re-skin
(editing app/theme.ts) still applies to every user who hasn't set their own.
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'c8e2a4f6b9d3'
down_revision: str | Sequence[str] | None = 'b1e6a9f3c7d2'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("brand_color", sa.String(length=7), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "brand_color")
