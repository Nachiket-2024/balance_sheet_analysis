"""Add comments to saved review reports."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "7d4e5f6a7b8c"
down_revision: str | Sequence[str] | None = "7c3d4e5f6a7b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "review_comments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("review_report_id", sa.Integer(), nullable=False),
        sa.Column("author_email", sa.String(length=320), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["review_report_id"], ["review_reports.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("id", "review_report_id", "author_email"):
        op.create_index(f"ix_review_comments_{column}", "review_comments", [column], unique=False)


def downgrade() -> None:
    op.drop_table("review_comments")
