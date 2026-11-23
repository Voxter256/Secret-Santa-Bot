"""add group left_at

Revision ID: cacc643c8d84
Revises: 77094013c363
Create Date: 2026-11-23 04:25:54.000000

Records when the bot lost access to a group, so dead exchanges can be
identified without deleting them. Reversible: re-adding the bot clears it.

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "cacc643c8d84"
down_revision: Union[str, Sequence[str], None] = "77094013c363"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(tablename: str, colname: str) -> bool:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return any(c["name"] == colname for c in inspector.get_columns(tablename))


def upgrade() -> None:
    """Upgrade schema."""
    if not _column_exists("groups", "left_at"):
        op.add_column("groups", sa.Column("left_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    if _column_exists("groups", "left_at"):
        op.drop_column("groups", "left_at")
