"""add_timestamps

Revision ID: 8e7acd69c2ad
Revises: 8c6885f97eae
Create Date: 2026-11-21 16:53:33.263632

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8e7acd69c2ad"
down_revision: Union[str, Sequence[str], None] = "8c6885f97eae"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(tablename: str, colname: str) -> bool:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return any(c["name"] == colname for c in inspector.get_columns(tablename))


def upgrade() -> None:
    """Upgrade schema."""
    # SQLite ALTER TABLE ADD COLUMN does not accept non-constant defaults
    # (e.g. CURRENT_TIMESTAMP), so we add as nullable then backfill.
    for table, col in (
        ("groups", "created_at"),
        ("links", "created_at"),
        ("links", "assigned_at"),
        ("participants", "created_at"),
    ):
        if not _column_exists(table, col):
            op.add_column(table, sa.Column(col, sa.DateTime(), nullable=True))

    # Backfill existing rows with the current timestamp
    for table in ("groups", "links", "participants"):
        if _column_exists(table, "created_at"):
            # `table` is drawn from the fixed literal tuple above, never user input.
            op.execute(f"UPDATE {table} SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL")  # noqa: S608


def downgrade() -> None:
    """Downgrade schema."""
    for table, col in (
        ("participants", "created_at"),
        ("links", "assigned_at"),
        ("links", "created_at"),
        ("groups", "created_at"),
    ):
        if _column_exists(table, col):
            op.drop_column(table, col)
