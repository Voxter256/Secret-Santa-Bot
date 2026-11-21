"""add_timestamps

Revision ID: 8e7acd69c2ad
Revises: 8c6885f97eae
Create Date: 2026-11-21 16:53:33.263632

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8e7acd69c2ad'
down_revision: Union[str, Sequence[str], None] = '8c6885f97eae'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # SQLite ALTER TABLE ADD COLUMN does not accept non-constant defaults
    # (e.g. CURRENT_TIMESTAMP), so we add as nullable then backfill.
    op.add_column('groups', sa.Column('created_at', sa.DateTime(), nullable=True))
    op.add_column('links', sa.Column('created_at', sa.DateTime(), nullable=True))
    op.add_column('links', sa.Column('assigned_at', sa.DateTime(), nullable=True))
    op.add_column('participants', sa.Column('created_at', sa.DateTime(), nullable=True))

    # Backfill existing rows with the current timestamp
    for table in ('groups', 'links', 'participants'):
        op.execute(f"UPDATE {table} SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL")


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('participants', 'created_at')
    op.drop_column('links', 'assigned_at')
    op.drop_column('links', 'created_at')
    op.drop_column('groups', 'created_at')