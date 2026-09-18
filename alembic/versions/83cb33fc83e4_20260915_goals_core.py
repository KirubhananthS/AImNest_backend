"""20260915_goals_core

Revision ID: 83cb33fc83e4
Revises: 76aaacfb8aec
Create Date: 2026-09-15 17:20:20.954895

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '83cb33fc83e4'
down_revision = '76aaacfb8aec'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'goals',
        sa.Column('id', sa.String(length=64), nullable=False),
        sa.Column('user_id', sa.String(length=64), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('category', sa.String(length=80), nullable=False),
        sa.Column('priority', sa.String(length=30), nullable=False),
        sa.Column('deadline', sa.Date(), nullable=False),
        sa.Column('status', sa.String(length=30), nullable=False),
        sa.Column('progress', sa.Integer(), nullable=False),
        sa.Column('completed', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_goals_user_id'), 'goals', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_goals_user_id'), table_name='goals')
    op.drop_table('goals')
