"""add_exchange_events

Revision ID: 1fdb5dcfc23c
Revises: 8e7acd69c2ad
Create Date: 2026-11-21 16:58:36.733812

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "1fdb5dcfc23c"
down_revision: str | Sequence[str] | None = "8e7acd69c2ad"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "exchange_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("timestamp", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("attempt_data", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["group_id"],
            ["groups.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_exchange_events_group_id"), "exchange_events", ["group_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_exchange_events_group_id"), table_name="exchange_events")
    op.drop_table("exchange_events")
