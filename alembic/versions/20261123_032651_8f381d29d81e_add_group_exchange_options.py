"""add group exchange options

Revision ID: 8f381d29d81e
Revises: 60e6fe52a838
Create Date: 2026-11-23 03:26:51.490224

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8f381d29d81e"
down_revision: Union[str, Sequence[str], None] = "60e6fe52a838"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(tablename: str, colname: str) -> bool:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return any(c["name"] == colname for c in inspector.get_columns(tablename))


def upgrade() -> None:
    """Upgrade schema."""
    added_requires_address = False
    if not _column_exists("groups", "requires_address"):
        op.add_column(
            "groups",
            sa.Column("requires_address", sa.Boolean(), nullable=False, server_default="0"),
        )
        added_requires_address = True
    if not _column_exists("groups", "wishlist_enabled"):
        op.add_column(
            "groups",
            sa.Column("wishlist_enabled", sa.Boolean(), nullable=False, server_default="0"),
        )
    if not _column_exists("groups", "title"):
        op.add_column("groups", sa.Column("title", sa.String(255), nullable=True))

    # Groups that already exist have been delivering addresses to their
    # participants, so keep that behaviour for them. The column default stays
    # 0, which means groups created after this migration opt in explicitly.
    if added_requires_address:
        op.execute("UPDATE groups SET requires_address = 1")


def downgrade() -> None:
    """Downgrade schema."""
    for column in ("title", "wishlist_enabled", "requires_address"):
        if _column_exists("groups", column):
            op.drop_column("groups", column)
