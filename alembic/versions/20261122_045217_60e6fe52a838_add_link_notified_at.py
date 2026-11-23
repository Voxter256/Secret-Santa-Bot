"""add link notified_at

Revision ID: 60e6fe52a838
Revises: 1fdb5dcfc23c
Create Date: 2026-11-22 04:52:17.995738

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "60e6fe52a838"
down_revision: str | Sequence[str] | None = "1fdb5dcfc23c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("links", sa.Column("notified_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("links", "notified_at")
