"""normalize the seeded user-lifecycle permission

Revision ID: f4a1c2e8b7d6
Revises: a7b8c9d0e1f2
"""
from collections.abc import Sequence

from alembic import op

revision: str = "f4a1c2e8b7d6"
down_revision: str | Sequence[str] | None = "a7b8c9d0e1f2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # A stale installation could have user_lifecycle carrying the old
    # soft-delete action (or the pre-rename users:purge action). Only this
    # named seeded policy is normalized: users:deactivate_any remains a
    # valid action everywhere else and must not be rewritten globally.
    op.execute(
        """
        UPDATE policies
        SET actions = ARRAY(
            SELECT action
            FROM unnest(
                array_replace(array_replace(actions, 'users:purge', 'users:delete_any'),
                              'users:deactivate_any', 'users:delete_any')
            ) WITH ORDINALITY AS normalized(action, position)
            GROUP BY action
            ORDER BY min(position)
        )
        WHERE name = 'user_lifecycle'
          AND (
              'users:purge' = ANY(actions)
              OR 'users:deactivate_any' = ANY(actions)
          )
        """
    )


def downgrade() -> None:
    # Restore the action name used by the migration that originally seeded
    # user_lifecycle. This is intentionally scoped to the named policy too;
    # a global users:delete_any downgrade would corrupt the hard-delete
    # permission introduced by the later rename migration.
    op.execute(
        """
        UPDATE policies
        SET actions = ARRAY(
            SELECT action
            FROM unnest(array_replace(actions, 'users:delete_any', 'users:purge'))
            WITH ORDINALITY AS restored(action, position)
            GROUP BY action
            ORDER BY min(position)
        )
        WHERE name = 'user_lifecycle'
          AND 'users:delete_any' = ANY(actions)
        """
    )
