"""Add alert notification policies, preferences, and delivery records."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "86a3b4c5d6e7"
down_revision: str | Sequence[str] | None = "85f2a3b4c5d6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "analysis_notification_policies",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("recipients", sa.JSON(), nullable=False),
        sa.Column("minimum_severity", sa.String(length=32), server_default="review", nullable=False),
        sa.Column("escalation_after_hours", sa.Integer(), server_default="0", nullable=False),
        sa.Column("escalation_recipients", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id"),
    )
    op.create_index("ix_analysis_notification_policies_id", "analysis_notification_policies", ["id"], unique=False)

    op.create_table(
        "analysis_notification_preferences",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_email", sa.String(length=320), nullable=False),
        sa.Column("email_enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_email"),
    )
    op.create_index("ix_analysis_notification_preferences_id", "analysis_notification_preferences", ["id"], unique=False)

    op.create_table(
        "analysis_notification_deliveries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("alert_id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("recipient", sa.String(length=320), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="queued", nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["alert_id"], ["analysis_alerts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("alert_id", "recipient", name="uq_analysis_notification_delivery_recipient"),
    )
    for column in ("id", "alert_id", "company_id", "recipient", "status"):
        op.create_index(f"ix_analysis_notification_deliveries_{column}", "analysis_notification_deliveries", [column], unique=False)


def downgrade() -> None:
    op.drop_table("analysis_notification_deliveries")
    op.drop_table("analysis_notification_preferences")
    op.drop_table("analysis_notification_policies")
