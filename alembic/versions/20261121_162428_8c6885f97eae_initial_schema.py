"""initial_schema

Revision ID: 8c6885f97eae
Revises:
Create Date: 2026-11-21 16:22:03.068417

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8c6885f97eae"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _create_table_if_not_exists(tablename: str, *args, **kwargs) -> None:
    """Create a table only if it doesn't already exist.

    Alembic's op.create_table chokes on existing tables.  On a fresh DB
    we run the DDL; on an existing DB the initial migration is only ever
    *stamped*, never *upgraded*.  Still, this guard prevents accidents.
    """
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if tablename not in inspector.get_table_names():
        op.create_table(tablename, *args, **kwargs)


def _create_index_if_not_exists(index_name: str, tablename: str, columns: list) -> None:
    """Create an index only if it doesn't already exist."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing = {ix["name"] for ix in inspector.get_indexes(tablename)}
    if index_name not in existing:
        op.create_index(index_name, tablename, columns)


def upgrade() -> None:
    """Upgrade schema."""
    # --- groups ---
    _create_table_if_not_exists(
        "groups",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("telegram_id", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    # --- participants ---
    _create_table_if_not_exists(
        "participants",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("telegram_id", sa.Integer(), nullable=True),
        sa.Column("telegram_username", sa.String(32), nullable=True),
        sa.Column("address", sa.String(1028), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    _create_index_if_not_exists("ix_participants_telegram_id", "participants", ["telegram_id"])
    _create_index_if_not_exists(
        "ix_participants_telegram_username",
        "participants",
        ["telegram_username"],
    )

    # --- links ---
    _create_table_if_not_exists(
        "links",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("santa_id", sa.Integer(), nullable=True),
        sa.Column("receiver_id", sa.Integer(), nullable=True),
        sa.Column("group_id", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    _create_index_if_not_exists("ix_links_santa_id", "links", ["santa_id"])
    _create_index_if_not_exists("ix_links_receiver_id", "links", ["receiver_id"])
    _create_index_if_not_exists("ix_links_group_id", "links", ["group_id"])

    # --- blocked_links ---
    _create_table_if_not_exists(
        "blocked_links",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("participant_id", sa.Integer(), nullable=True),
        sa.Column("blocked_username", sa.String(32), nullable=True),
        sa.Column("blocked_id", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    _create_index_if_not_exists(
        "ix_blocked_links_participant_id",
        "blocked_links",
        ["participant_id"],
    )
    _create_index_if_not_exists(
        "ix_blocked_links_blocked_username",
        "blocked_links",
        ["blocked_username"],
    )
    _create_index_if_not_exists("ix_blocked_links_blocked_id", "blocked_links", ["blocked_id"])

    # --- wishlist_items ---
    _create_table_if_not_exists(
        "wishlist_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("participant_id", sa.Integer(), nullable=True),
        sa.Column("details", sa.String(2048), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    _create_index_if_not_exists(
        "ix_wishlist_items_participant_id",
        "wishlist_items",
        ["participant_id"],
    )


def downgrade() -> None:
    """Downgrade schema.

    Only drops tables that exist — safe to run on a populated DB.
    """
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing = set(inspector.get_table_names())

    for table in ("wishlist_items", "blocked_links", "links", "participants", "groups"):
        if table in existing:
            op.drop_table(table)
