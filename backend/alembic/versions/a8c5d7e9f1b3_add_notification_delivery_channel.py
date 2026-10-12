"""Add notification delivery channel metadata."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a8c5d7e9f1b3"
down_revision: str | Sequence[str] | None = "97b4c6d8e1f2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("analysis_notification_deliveries", sa.Column("channel", sa.String(length=32), server_default="email", nullable=False))
    op.create_index("ix_analysis_notification_deliveries_channel", "analysis_notification_deliveries", ["channel"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_analysis_notification_deliveries_channel", table_name="analysis_notification_deliveries")
    op.drop_column("analysis_notification_deliveries", "channel")
