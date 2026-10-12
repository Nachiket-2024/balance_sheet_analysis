"""rename users:delete_any/users:purge action strings

Revision ID: a4c8f1d92b6e
Revises: 6d6c9f178682
Create Date: 2026-09-16 00:00:00.000000

Data-only migration: renames the two stored action strings to match
authorization/permissions.py's Permission enum, which this same change
renames so the identifiers read consistently with their UI labels
(Deactivate/Delete) instead of the old, mismatched delete_any/purge pair:

    users:delete_any (soft-delete/"Deactivate")  -> users:deactivate_any
    users:purge       (hard-delete/"Delete")     -> users:delete_any

Rewrites both storage locations these actions can live in: `policies.actions`
(a Postgres text array, updated with array_replace) and `user_permissions.action`
(a plain string column, updated with a WHERE match) - a direct UserPermission
grant bypasses Policy entirely, so both need the same rename or one of the two
grant paths would silently stop matching after this deploys.

Order matters within each table: the old `users:delete_any` is renamed to
`users:deactivate_any` FIRST, before the old `users:purge` is renamed to the
now-vacated `users:delete_any` SECOND. Doing it in the other order would
briefly leave two different meanings under the same string and the first
UPDATE's WHERE clause would incorrectly catch rows the second UPDATE was
meant to touch.
"""
from collections.abc import Sequence

from alembic import op

revision: str = "a4c8f1d92b6e"
down_revision: str | None = "6d6c9f178682"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    # policies.actions (array column)
    op.execute(
        "UPDATE policies SET actions = array_replace(actions, 'users:delete_any', 'users:deactivate_any') "
        "WHERE 'users:delete_any' = ANY(actions)"
    )
    op.execute(
        "UPDATE policies SET actions = array_replace(actions, 'users:purge', 'users:delete_any') "
        "WHERE 'users:purge' = ANY(actions)"
    )

    # user_permissions.action (plain string column)
    op.execute("UPDATE user_permissions SET action = 'users:deactivate_any' WHERE action = 'users:delete_any'")
    op.execute("UPDATE user_permissions SET action = 'users:delete_any' WHERE action = 'users:purge'")


def downgrade() -> None:
    # Reverse order: undo the second rename first, so the first rename's
    # WHERE clause can't re-catch what the second one just produced.
    op.execute(
        "UPDATE policies SET actions = array_replace(actions, 'users:delete_any', 'users:purge') "
        "WHERE 'users:delete_any' = ANY(actions)"
    )
    op.execute(
        "UPDATE policies SET actions = array_replace(actions, 'users:deactivate_any', 'users:delete_any') "
        "WHERE 'users:deactivate_any' = ANY(actions)"
    )

    op.execute("UPDATE user_permissions SET action = 'users:purge' WHERE action = 'users:delete_any'")
    op.execute("UPDATE user_permissions SET action = 'users:delete_any' WHERE action = 'users:deactivate_any'")
