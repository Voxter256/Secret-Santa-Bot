"""Migration runner — shared between run.py and tests."""

import logging
import os

from alembic import command
from alembic.config import Config


def run_migrations(db_url: str) -> None:
    """Run all pending Alembic migrations against *db_url*.

    Safe to call on every startup — Alembic skips already-applied
    revisions.  Raises on failure so the caller knows the DB is in
    an unknown state.
    """
    os.environ["DATABASE_URL"] = db_url
    alembic_cfg = Config("alembic.ini")
    try:
        command.upgrade(alembic_cfg, "head")
    except Exception:
        logging.getLogger(__name__).exception(
            "Database migration failed for %s", db_url
        )
        raise