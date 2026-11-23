"""add link foreign keys

Revision ID: b21f5c7d90aa
Revises: d7867b789a16
Create Date: 2026-11-23 07:15:00.000000

The initial schema created ``links`` and ``blocked_links`` without the foreign
keys the models declare, so a database built from migrations had no integrity
constraints on those tables while one created by ``create_all`` did. SQLite
cannot add a constraint with ALTER TABLE, so the tables are rebuilt in batch
mode; existing rows are copied, and named constraints are used so the downgrade
can drop exactly the ones this revision added.

Both directions skip a table whose constraint is already present. That is the
case for ``bot.sqlite``, which predates the migration system and already
carries the constraints from ``create_all``.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b21f5c7d90aa"
down_revision: str | Sequence[str] | None = "d7867b789a16"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# table -> (constraint name, local column, referenced table)
FOREIGN_KEYS: dict[str, tuple[tuple[str, str, str], ...]] = {
    "links": (
        ("fk_links_santa_id", "santa_id", "participants"),
        ("fk_links_receiver_id", "receiver_id", "participants"),
        ("fk_links_group_id", "group_id", "groups"),
    ),
    "blocked_links": (
        ("fk_blocked_links_participant_id", "participant_id", "participants"),
        ("fk_blocked_links_blocked_id", "blocked_id", "participants"),
    ),
}


def _existing_foreign_keys(inspector: sa.Inspector, table: str) -> dict[tuple[str, ...], str | None]:
    return {tuple(fk["constrained_columns"]): fk["name"] for fk in inspector.get_foreign_keys(table)}


def _recreate_table(table: str):
    """Open a batch context for a reflected copy of ``table``."""
    conn = op.get_bind()
    reflected = sa.Table(table, sa.MetaData(), autoload_with=conn)
    return op.batch_alter_table(table, copy_from=reflected)


def upgrade() -> None:
    """Add the constraints that are missing, preserving existing rows."""
    conn = op.get_bind()
    for table, specs in FOREIGN_KEYS.items():
        existing = _existing_foreign_keys(sa.inspect(conn), table)
        missing = [spec for spec in specs if (spec[1],) not in existing]
        if not missing:
            continue
        with _recreate_table(table) as batch:
            for name, column, target in missing:
                batch.create_foreign_key(name, target, [column], ["id"])


def downgrade() -> None:
    """Drop only the named constraints this revision created."""
    conn = op.get_bind()
    for table, specs in FOREIGN_KEYS.items():
        existing = _existing_foreign_keys(sa.inspect(conn), table)
        ours = [name for name, column, _target in specs if existing.get((column,)) == name]
        if not ours:
            continue
        with _recreate_table(table) as batch:
            for name in ours:
                batch.drop_constraint(name, type_="foreignkey")
