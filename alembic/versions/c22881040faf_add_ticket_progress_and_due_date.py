"""add ticket progress and due date

Revision ID: c22881040faf
Revises: 07a2ca74fe1d
Create Date: 2026-09-28 04:32:12.271275

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c22881040faf"
down_revision = "07a2ca74fe1d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tickets",
        sa.Column(
            "progress",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )

    op.add_column(
        "tickets",
        sa.Column(
            "due_date",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("tickets", "due_date")
    op.drop_column("tickets", "progress")