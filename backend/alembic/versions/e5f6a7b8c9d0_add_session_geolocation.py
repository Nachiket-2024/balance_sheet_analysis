"""add city/country geolocation columns to user_sessions

Revision ID: e5f6a7b8c9d0
Revises: c4d5e6f7a8b9
Create Date: 2026-08-19 00:00:01.000000

Adds nullable city/country columns to user_sessions, populated best-effort
at session create/rotate time from the login IP (see user_session/session_geolocation.py)
via a local MaxMind GeoLite2-City database. Nullable, same as ip_address
itself: not every login has a resolvable IP, and lookups fail open (never
block login) when the database file is absent or the address can't be
resolved. See session_service.py's create_session/rotate_session/
rotate_session_by_chain and ManageSessionsCard.tsx's new Location column.
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'e5f6a7b8c9d0'
down_revision: str | Sequence[str] | None = 'c4d5e6f7a8b9'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('user_sessions', sa.Column('city', sa.String(), nullable=True))
    op.add_column('user_sessions', sa.Column('country', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('user_sessions', 'country')
    op.drop_column('user_sessions', 'city')
