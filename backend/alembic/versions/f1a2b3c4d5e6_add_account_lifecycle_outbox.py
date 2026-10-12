"""add durable account lifecycle outbox

Revision ID: f1a2b3c4d5e6
Revises: c2d3e4f5a6b7
"""
import sqlalchemy as sa

from alembic import op

revision: str = "f1a2b3c4d5e6"
down_revision: str | None = "c2d3e4f5a6b7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "account_lifecycle_outbox",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("user_email", sa.String(), nullable=False),
        sa.Column("actor", sa.String(), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("queued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_account_lifecycle_outbox_event_type", "account_lifecycle_outbox", ["event_type"])
    op.create_index("ix_account_lifecycle_outbox_user_email", "account_lifecycle_outbox", ["user_email"])


def downgrade() -> None:
    op.drop_index("ix_account_lifecycle_outbox_user_email", table_name="account_lifecycle_outbox")
    op.drop_index("ix_account_lifecycle_outbox_event_type", table_name="account_lifecycle_outbox")
    op.drop_table("account_lifecycle_outbox")
