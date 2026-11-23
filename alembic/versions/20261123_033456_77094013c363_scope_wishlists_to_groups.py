"""scope wishlists to groups

Revision ID: 77094013c363
Revises: 8f381d29d81e
Create Date: 2026-11-23 03:34:56.000000

The original table was keyed only on the participant, which cannot express
"a different wishlist per exchange". It has never held a row, so it is
recreated rather than migrated.

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "77094013c363"
down_revision: str | Sequence[str] | None = "8f381d29d81e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_table("wishlist_items")
    op.create_table(
        "wishlist_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("group_id", sa.Integer(), sa.ForeignKey("groups.id"), nullable=False),
        sa.Column("participant_id", sa.Integer(), sa.ForeignKey("participants.id"), nullable=False),
        sa.Column("details", sa.String(2048), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index(
        "ix_wishlist_items_group_participant",
        "wishlist_items",
        ["group_id", "participant_id"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("wishlist_items")
    op.create_table(
        "wishlist_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("participant_id", sa.Integer(), sa.ForeignKey("participants.id"), nullable=True),
        sa.Column("details", sa.String(2048), nullable=True),
    )
    op.create_index("ix_wishlist_items_participant_id", "wishlist_items", ["participant_id"])
