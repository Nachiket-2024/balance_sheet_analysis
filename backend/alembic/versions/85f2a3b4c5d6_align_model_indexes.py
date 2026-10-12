"""Align generated indexes with the SQLAlchemy models."""

from collections.abc import Sequence

from alembic import op

revision: str = "85f2a3b4c5d6"
down_revision: str | Sequence[str] | None = "84e1f2a3b4c5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index("ix_analysis_settings_history_created_at", table_name="analysis_settings_history")
    op.drop_index("ix_company_analysis_settings_company_id", table_name="company_analysis_settings")
    op.create_index("ix_review_assignments_assigned_by_email", "review_assignments", ["assigned_by_email"], unique=False)
    op.drop_index("ix_review_signoffs_status", table_name="review_signoffs")


def downgrade() -> None:
    op.drop_index("ix_review_assignments_assigned_by_email", table_name="review_assignments")
    op.create_index("ix_review_signoffs_status", "review_signoffs", ["status"], unique=False)
    op.create_index("ix_company_analysis_settings_company_id", "company_analysis_settings", ["company_id"], unique=True)
    op.create_index("ix_analysis_settings_history_created_at", "analysis_settings_history", ["created_at"], unique=False)
