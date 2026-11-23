"""add feedback

Revision ID: d7867b789a16
Revises: cacc643c8d84
Create Date: 2026-11-23 05:39:34.395606

Stores free-text messages sent with /feedback. The row is written before the
message is forwarded to the owner's chat, so a failed send loses nothing;
``forwarded_at`` stays NULL until the forward succeeds.

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d7867b789a16"
down_revision: Union[str, Sequence[str], None] = "cacc643c8d84"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(tablename: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(tablename)


def _index_exists(index_name: str, tablename: str) -> bool:
    conn = op.get_bind()
    return any(i["name"] == index_name for i in sa.inspect(conn).get_indexes(tablename))


def upgrade() -> None:
    """Upgrade schema."""
    if not _table_exists("feedback"):
        op.create_table(
            "feedback",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("telegram_id", sa.Integer(), nullable=False),
            sa.Column("telegram_username", sa.String(length=32), nullable=True),
            sa.Column("chat_id", sa.Integer(), nullable=True),
            sa.Column("body", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
            sa.Column("forwarded_at", sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
    if not _index_exists("ix_feedback_telegram_id", "feedback"):
        op.create_index("ix_feedback_telegram_id", "feedback", ["telegram_id"])


def downgrade() -> None:
    """Downgrade schema."""
    if _index_exists("ix_feedback_telegram_id", "feedback"):
        op.drop_index("ix_feedback_telegram_id", table_name="feedback")
    if _table_exists("feedback"):
        op.drop_table("feedback")
