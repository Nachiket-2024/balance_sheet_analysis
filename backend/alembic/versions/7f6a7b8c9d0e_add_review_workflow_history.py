"""Add review assignments and sign-off history."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "7f6a7b8c9d0e"
down_revision: str | Sequence[str] | None = "7e5f6a7b8c9d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _create(name: str, columns: list[sa.Column], indexes: tuple[str, ...]) -> None:
    op.create_table(name, *columns, sa.PrimaryKeyConstraint("id"), sa.ForeignKeyConstraint(["review_report_id"], ["review_reports.id"], ondelete="CASCADE"))
    for column in indexes:
        op.create_index(f"ix_{name}_{column}", name, [column], unique=False)


def upgrade() -> None:
    _create("review_assignments", [
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("review_report_id", sa.Integer(), nullable=False),
        sa.Column("assigned_to_email", sa.String(length=320), nullable=False),
        sa.Column("assigned_by_email", sa.String(length=320), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    ], ("id", "review_report_id", "assigned_to_email"))
    _create("review_signoffs", [
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("review_report_id", sa.Integer(), nullable=False),
        sa.Column("actor_email", sa.String(length=320), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    ], ("id", "review_report_id", "actor_email", "status"))


def downgrade() -> None:
    op.drop_table("review_signoffs")
    op.drop_table("review_assignments")
