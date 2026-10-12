"""add last_login_at column to users

Revision ID: b1c2d3e4f5a6
Revises: a4c8f1d92b6e
Create Date: 2026-09-18 00:00:00.000000

Adds a nullable last_login_at timestamp to users, set on every successful
sign-in (password or OAuth2, see login_service.py/oauth2_service.py).
Nullable: an account that has never signed in (e.g. created by an admin)
has no value here. Backs the Users page's "Last login" column/filter
(design/users.html).
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b1c2d3e4f5a6'
down_revision: str | Sequence[str] | None = 'a4c8f1d92b6e'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('users', sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'last_login_at')
