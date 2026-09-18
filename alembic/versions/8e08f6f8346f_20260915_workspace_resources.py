"""20260915_workspace_resources

Revision ID: 8e08f6f8346f
Revises: 07d0d0fede31
Create Date: 2026-09-15 17:05:27.920071

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8e08f6f8346f'
down_revision = '07d0d0fede31'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'workspace_resources',
        sa.Column('id', sa.String(length=64), nullable=False),
        sa.Column('workspace_id', sa.String(length=64), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('size', sa.String(length=50), nullable=True),
        sa.Column('type', sa.String(length=30), nullable=False),
        sa.Column('icon', sa.String(length=80), nullable=True),
        sa.Column('color', sa.String(length=30), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_workspace_resources_workspace_id'), 'workspace_resources', ['workspace_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_workspace_resources_workspace_id'), table_name='workspace_resources')
    op.drop_table('workspace_resources')
