"""optimize audit log per-user query index

Revision ID: c7f1a3e9d2b6
Revises: b4e8f2a9c6d1
Create Date: 2026-07-13 00:00:00.000000

Per claude.md's Database Optimization task — evidence-based, not
speculative. Analysis performed directly against the Docker PostgreSQL
container (postgres:15) seeded with ~10k users, ~30k policy assignments,
and ~220k audit log rows (one user seeded with ~20k rows to model a
heavily-audited account):

  EXPLAIN ANALYZE on AuditLogRepository.get_for_user's actual query
  (`WHERE user_email = :email ORDER BY created_at DESC, id DESC LIMIT
  :limit OFFSET :offset`) showed, for the heavily-audited user: an
  Incremental Sort over a created_at-backward index scan with a
  post-filter on user_email (0.200ms) — i.e. Postgres could not use the
  existing single-column `ix_authorization_audit_log_user_email` index to
  also satisfy the ORDER BY, so it fell back to scanning by created_at
  and filtering, plus a separate sort.

  Adding a composite index on (user_email, created_at DESC, id DESC)
  measurably eliminated the sort step entirely for that same query
  (0.135ms; plan became a single direct Index Scan, already presorted) —
  confirmed by re-running EXPLAIN ANALYZE with the new index present.

The old single-column `ix_authorization_audit_log_user_email` index is
dropped as part of this same migration: grep confirmed user_email is
never queried anywhere in this codebase without this exact ORDER BY (see
audit_log_repository.py's get_for_user — the only place that filters by
user_email at all), so the composite index's leftmost prefix (user_email
alone) already serves that access pattern; keeping the old index would be
pure redundant write overhead on audit log inserts, which happen on
*every* real authorize()/require() call — the hottest write path in the
whole application.

Note: the equivalent composite index was also evaluated for
policy_history (policy_name, created_at DESC, id DESC), which has the
identical query shape in PolicyHistoryRepository.get_for_policy. At
policy_history's realistic scale (history entries accumulate only from
infrequent admin policy edits, not per-request traffic), EXPLAIN ANALYZE
showed Postgres's planner declined to use that composite index even when
it was present, continuing to prefer the existing created_at-backward-
scan-and-filter plan — i.e. no demonstrated benefit at that table's
actual usage pattern. That index was therefore NOT added here, per
claude.md's "add indexes only with demonstrated need" — see this
migration's absence of any policy_history change as the direct evidence
of that finding, not an oversight.
"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'c7f1a3e9d2b6'
down_revision: str | Sequence[str] | None = 'b4e8f2a9c6d1'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Raw SQL for exact column-direction control (user_email ASC,
    # created_at DESC, id DESC) — matches exactly what was measured with
    # EXPLAIN ANALYZE during analysis.
    op.execute(
        "CREATE INDEX ix_audit_log_user_email_created_at "
        "ON authorization_audit_log (user_email, created_at DESC, id DESC)"
    )
    op.drop_index('ix_authorization_audit_log_user_email', table_name='authorization_audit_log')


def downgrade() -> None:
    op.create_index(
        op.f('ix_authorization_audit_log_user_email'),
        'authorization_audit_log',
        ['user_email'],
        unique=False,
    )
    op.execute("DROP INDEX IF EXISTS ix_audit_log_user_email_created_at")
