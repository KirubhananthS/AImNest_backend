"""20260915_goal_milestones

Revision ID: 4888093b2c94
Revises: e62b6a70fd59
Create Date: 2026-09-15 17:30:42.401621

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4888093b2c94'
down_revision = 'e62b6a70fd59'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'goal_milestones',
        sa.Column('id', sa.String(length=64), nullable=False),
        sa.Column('goal_id', sa.String(length=64), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('status', sa.String(length=30), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['goal_id'], ['goals.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_goal_milestones_goal_id'), 'goal_milestones', ['goal_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_goal_milestones_goal_id'), table_name='goal_milestones')
    op.drop_table('goal_milestones')
