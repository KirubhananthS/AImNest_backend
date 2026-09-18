"""20260915_workspace_tasks

Revision ID: 07d0d0fede31
Revises: 18780392b770
Create Date: 2026-09-15 17:00:24.229440

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '07d0d0fede31'
down_revision = '18780392b770'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'workspace_tasks',
        sa.Column('id', sa.String(length=64), nullable=False),
        sa.Column('workspace_id', sa.String(length=64), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=30), nullable=False),
        sa.Column('priority', sa.String(length=30), nullable=False),
        sa.Column('due_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_workspace_tasks_workspace_id'), 'workspace_tasks', ['workspace_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_workspace_tasks_workspace_id'), table_name='workspace_tasks')
    op.drop_table('workspace_tasks')
