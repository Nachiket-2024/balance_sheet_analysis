"""optimize security audit log per-user query index

Revision ID: e7a2c4d8f1b3
Revises: c8e2a4f6b9d3
Create Date: 2026-08-21 00:00:00.000000

Same fix as c7f1a3e9d2b6 (authorization_audit_log), applied here to
security_audit_log: AuditLogRepository.get_for_user runs `WHERE user_email
= :email ORDER BY created_at DESC, id DESC LIMIT :limit OFFSET :offset`,
the same shape c7f1a3e9d2b6 measured on authorization_audit_log. The
single-column `ix_security_audit_log_user_email` index cannot also satisfy
that ORDER BY, so Postgres falls back to scanning by created_at with a
post-filter on user_email plus a separate sort, exactly the plan
c7f1a3e9d2b6's EXPLAIN ANALYZE evidence describes for the sibling table.

security_audit_log received its own get_for_user (GET /audit-log/me,
audit_log_routes.py) after c7f1a3e9d2b6 shipped, so this index was never
added at the time. Adding the composite (user_email, created_at DESC, id
DESC) index and dropping the now-redundant single-column user_email index,
for the same reasons c7f1a3e9d2b6 gives: its leftmost prefix already
serves a plain user_email lookup, and keeping both would be pure
redundant write overhead on every login/logout/signup event.
"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'e7a2c4d8f1b3'
down_revision: str | Sequence[str] | None = 'c8e2a4f6b9d3'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "CREATE INDEX ix_security_audit_log_user_email_created_at "
        "ON security_audit_log (user_email, created_at DESC, id DESC)"
    )
    op.drop_index('ix_security_audit_log_user_email', table_name='security_audit_log')


def downgrade() -> None:
    op.create_index(
        op.f('ix_security_audit_log_user_email'),
        'security_audit_log',
        ['user_email'],
        unique=False,
    )
    op.execute("DROP INDEX IF EXISTS ix_security_audit_log_user_email_created_at")
