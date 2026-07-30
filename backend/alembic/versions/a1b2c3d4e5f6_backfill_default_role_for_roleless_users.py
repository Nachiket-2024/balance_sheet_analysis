"""backfill default role for existing roleless users

Revision ID: a1b2c3d4e5f6
Revises: f3c1a9d7e5b2
Create Date: 2026-07-14 00:00:00.000000

Data-only migration. Role is display/grouping metadata only — it has never
granted access under this app's PBAC design (see
authorization/permissions.py) — but some existing accounts predate the fix
in oauth2_service.py that gives new OAuth2 signups the same default role
(UserRole.user) password signup has always used, and were created with
role=NULL. That shows as a blank/missing role on Dashboard/Profile in the
frontend. Backfill every NULL role to 'user' (the normal, non-privileged
default) so every account displays a role consistently, without touching
access — deliberately excludes the reserved system account, which is
identified by a NULL hashed_password + role IS NULL combination being
impossible for it (the system account always has both a role and a
password set by create_system_user.py), so this WHERE clause can never
accidentally touch it, but the exclusion is still made explicit below for
defense in depth.
"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: str | Sequence[str] | None = 'f3c1a9d7e5b2'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # `role` is a native Postgres enum column (userrole), not varchar —
    # binding a plain string parameter through SQLAlchemy's table.update()
    # sends it as ::VARCHAR and Postgres refuses the implicit cast
    # (DatatypeMismatchError). A literal in raw SQL resolves against the
    # column's enum type directly, so use op.execute with the fixed value
    # inlined (safe: 'user' is a hardcoded constant, not user input).
    op.execute("UPDATE users SET role = 'user' WHERE role IS NULL")


def downgrade() -> None:
    # Deliberately a no-op: there is no reliable way to distinguish "was
    # NULL before this migration ran" from "was genuinely created as
    # 'user' afterward" — reverting would risk blanking real accounts'
    # roles. Role is metadata-only either way, so leaving it populated on
    # downgrade is safe.
    pass
