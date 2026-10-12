"""Add audit history for management analysis setting changes."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "84e1f2a3b4c5"
down_revision: str | Sequence[str] | None = "83d0e1f2a3b4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "analysis_settings_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("changed_by", sa.String(length=320), nullable=False),
        sa.Column("thresholds", sa.JSON(), nullable=False),
        sa.Column("target_currency", sa.String(length=8), nullable=True),
        sa.Column("display_scale", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("id", "company_id", "changed_by", "created_at"):
        op.create_index(f"ix_analysis_settings_history_{column}", "analysis_settings_history", [column], unique=False)


def downgrade() -> None:
    op.drop_table("analysis_settings_history")
