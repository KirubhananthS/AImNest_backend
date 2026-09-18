"""20260915_goal_tasks

Revision ID: e62b6a70fd59
Revises: 83cb33fc83e4
Create Date: 2026-09-15 17:26:15.349879

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e62b6a70fd59'
down_revision = '83cb33fc83e4'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'goal_tasks',
        sa.Column('id', sa.String(length=64), nullable=False),
        sa.Column('goal_id', sa.String(length=64), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=30), nullable=False),
        sa.Column('due_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['goal_id'], ['goals.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_goal_tasks_goal_id'), 'goal_tasks', ['goal_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_goal_tasks_goal_id'), table_name='goal_tasks')
    op.drop_table('goal_tasks')
