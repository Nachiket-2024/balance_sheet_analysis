"""Add company review thresholds and durable analysis alerts."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "81b8c9d0e1f2"
down_revision: str | Sequence[str] | None = "80a7b8c9d0e1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "company_analysis_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("thresholds", sa.JSON(), server_default=sa.text("'{}'"), nullable=False),
        sa.Column("target_currency", sa.String(length=8), nullable=True),
        sa.Column("display_scale", sa.Float(), server_default="1", nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id"),
    )
    op.create_index("ix_company_analysis_settings_id", "company_analysis_settings", ["id"], unique=False)
    op.create_index("ix_company_analysis_settings_company_id", "company_analysis_settings", ["company_id"], unique=True)

    op.create_table(
        "analysis_alerts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("alert_key", sa.String(length=255), nullable=False),
        sa.Column("alert_type", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.String(length=32), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("years", sa.JSON(), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="open", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("acknowledged_by", sa.String(length=320), nullable=True),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "alert_key", name="uq_analysis_alert_company_key"),
    )
    for column in ("id", "company_id", "alert_type", "severity", "status"):
        op.create_index(f"ix_analysis_alerts_{column}", "analysis_alerts", [column], unique=False)


def downgrade() -> None:
    op.drop_table("analysis_alerts")
    op.drop_table("company_analysis_settings")
