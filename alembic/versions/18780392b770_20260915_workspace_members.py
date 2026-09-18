"""20260915_workspace_members

Revision ID: 18780392b770
Revises: 7e6296e55ce1
Create Date: 2026-09-15 16:51:33.850957

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '18780392b770'
down_revision = '7e6296e55ce1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'workspace_members',
        sa.Column('id', sa.String(length=64), nullable=False),
        sa.Column('workspace_id', sa.String(length=64), nullable=False),
        sa.Column('user_id', sa.String(length=64), nullable=False),
        sa.Column('role', sa.String(length=50), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('workspace_id', 'user_id', name='uq_workspace_members_workspace_user'),
    )
    op.create_index(op.f('ix_workspace_members_workspace_id'), 'workspace_members', ['workspace_id'], unique=False)
    op.create_index(op.f('ix_workspace_members_user_id'), 'workspace_members', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_workspace_members_user_id'), table_name='workspace_members')
    op.drop_index(op.f('ix_workspace_members_workspace_id'), table_name='workspace_members')
    op.drop_table('workspace_members')
