"""20260914_workspace_core

Revision ID: 7e6296e55ce1
Revises: 20260914_0001
Create Date: 2026-09-14 15:04:49.022152

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7e6296e55ce1'
down_revision = '20260914_0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'workspaces',
        sa.Column('id', sa.String(length=64), nullable=False),
        sa.Column('owner_id', sa.String(length=64), nullable=False),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('description', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ondelete='CASCADE'),
    )
    op.create_index(op.f('ix_workspaces_owner_id'), 'workspaces', ['owner_id'], unique=False)
    op.create_index(op.f('ix_workspaces_name'), 'workspaces', ['name'], unique=False)

def downgrade() -> None:
    op.drop_index(op.f('ix_workspaces_name'), table_name='workspaces')
    op.drop_index(op.f('ix_workspaces_owner_id'), table_name='workspaces')
    op.drop_table('workspaces')
