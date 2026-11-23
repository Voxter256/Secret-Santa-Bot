"""Migration runner — shared between run.py and tests."""

import logging
import pathlib

from alembic import command
from alembic.config import Config
from sqlalchemy.engine import Connection

ALEMBIC_INI = pathlib.Path(__file__).resolve().parent.parent / "alembic.ini"


def run_migrations(db_url: str, connection: Connection | None = None, revision: str = "head") -> None:
    """Run Alembic migrations against *db_url*, up to *revision*.

    Safe to call on every startup — Alembic skips already-applied
    revisions.  Raises on failure so the caller knows the DB is in
    an unknown state.

    Pass *connection* to migrate through an existing connection, which is
    required for in-memory SQLite: each new connection to ``:memory:`` opens
    a separate database, so Alembic must reuse the caller's.

    Pass *revision* to stop at a specific revision. Tests use this to seed
    data against an older schema and then upgrade, which is how the data
    backfills get exercised.
    """
    alembic_cfg = Config(str(ALEMBIC_INI))
    # Explicit arguments beat the environment, which beats alembic.ini.
    alembic_cfg.attributes["db_url"] = db_url
    if connection is not None:
        alembic_cfg.attributes["connection"] = connection
    try:
        command.upgrade(alembic_cfg, revision)
    except Exception:
        logging.getLogger(__name__).exception("Database migration failed for %s", db_url)
        raise
