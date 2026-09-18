"""20260915_workspace_activity

Revision ID: 76aaacfb8aec
Revises: 8e08f6f8346f
Create Date: 2026-09-15 17:10:15.814609

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '76aaacfb8aec'
down_revision = '8e08f6f8346f'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'workspace_activities',
        sa.Column('id', sa.String(length=64), nullable=False),
        sa.Column('workspace_id', sa.String(length=64), nullable=False),
        sa.Column('user_id', sa.String(length=64), nullable=True),
        sa.Column('action', sa.String(length=80), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_workspace_activities_workspace_id'), 'workspace_activities', ['workspace_id'], unique=False)
    op.create_index(op.f('ix_workspace_activities_user_id'), 'workspace_activities', ['user_id'], unique=False)
    op.create_index(op.f('ix_workspace_activities_created_at'), 'workspace_activities', ['created_at'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_workspace_activities_created_at'), table_name='workspace_activities')
    op.drop_index(op.f('ix_workspace_activities_user_id'), table_name='workspace_activities')
    op.drop_index(op.f('ix_workspace_activities_workspace_id'), table_name='workspace_activities')
    op.drop_table('workspace_activities')
