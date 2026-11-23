"""Migration tests that need their own database, kept out of the handler suite."""

import os
import tempfile
import unittest

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from bot._migrate import run_migrations


class TestLinkForeignKeyMigration(unittest.TestCase):
    """The baseline omitted the FKs on links/blocked_links; b21f5c7d90aa adds them."""

    PARENT = "d7867b789a16"
    HEAD = "b21f5c7d90aa"
    LINK_FKS = {("santa_id",), ("receiver_id",), ("group_id",)}
    BLOCKED_FKS = {("participant_id",), ("blocked_id",)}

    # The pre-patch baseline tables, without any foreign keys on links/blocked_links.
    DRIFT_DDL = (
        "CREATE TABLE groups (id INTEGER NOT NULL, telegram_id INTEGER, PRIMARY KEY (id))",
        "CREATE TABLE participants (id INTEGER NOT NULL, telegram_id INTEGER, PRIMARY KEY (id))",
        "CREATE TABLE links (id INTEGER NOT NULL, santa_id INTEGER, receiver_id INTEGER, "
        "group_id INTEGER, created_at DATETIME, assigned_at DATETIME, notified_at DATETIME, "
        "PRIMARY KEY (id))",
        "CREATE INDEX ix_links_santa_id ON links (santa_id)",
        "CREATE INDEX ix_links_receiver_id ON links (receiver_id)",
        "CREATE INDEX ix_links_group_id ON links (group_id)",
        "CREATE TABLE blocked_links (id INTEGER NOT NULL, participant_id INTEGER, "
        "blocked_username VARCHAR(32), blocked_id INTEGER, PRIMARY KEY (id))",
        "CREATE INDEX ix_blocked_links_participant_id ON blocked_links (participant_id)",
        "CREATE INDEX ix_blocked_links_blocked_username ON blocked_links (blocked_username)",
        "CREATE INDEX ix_blocked_links_blocked_id ON blocked_links (blocked_id)",
    )

    def setUp(self) -> None:
        fd, path = tempfile.mkstemp(suffix=".sqlite")
        os.close(fd)
        self._path = path
        self.db_url = f"sqlite:///{path}"

    def tearDown(self) -> None:
        os.unlink(self._path)

    def _upgrade(self, revision: str = "head") -> None:
        run_migrations(self.db_url, revision=revision)

    def _downgrade(self, revision: str) -> None:
        config = Config("alembic.ini")
        config.attributes["db_url"] = self.db_url
        command.downgrade(config, revision)

    def _drift_database(self) -> None:
        """Recreate the pre-patch schema and stamp it at the parent revision."""
        engine = create_engine(self.db_url)
        try:
            with engine.begin() as connection:
                connection.execute(
                    text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL, PRIMARY KEY (version_num))")
                )
                connection.execute(
                    text(f"INSERT INTO alembic_version (version_num) VALUES ('{self.PARENT}')")  # noqa: S608
                )
                for ddl in self.DRIFT_DDL:
                    connection.execute(text(ddl))
                connection.execute(text("INSERT INTO participants (id, telegram_id) VALUES (10, 100), (11, 101)"))
                connection.execute(text("INSERT INTO groups (id, telegram_id) VALUES (1, 1000)"))
                connection.execute(
                    text(
                        "INSERT INTO links (id, santa_id, receiver_id, group_id) VALUES (1, 10, 11, 1), (2, 11, 10, 1)"
                    )
                )
                connection.execute(
                    text("INSERT INTO blocked_links (id, participant_id, blocked_id) VALUES (1, 10, 11)")
                )
        finally:
            engine.dispose()

    # Reflection is cached per engine in SQLAlchemy 2.1 and the migrations run
    # through Alembic's own engine, so every read takes a fresh engine.
    def _fk_columns(self, table: str) -> set[tuple[str, ...]]:
        engine = create_engine(self.db_url)
        try:
            return {tuple(fk["constrained_columns"]) for fk in inspect(engine).get_foreign_keys(table)}
        finally:
            engine.dispose()

    def _index_names(self, table: str) -> set[str]:
        engine = create_engine(self.db_url)
        try:
            return {ix["name"] for ix in inspect(engine).get_indexes(table)}
        finally:
            engine.dispose()

    def _scalar(self, statement: str):
        engine = create_engine(self.db_url)
        try:
            with engine.connect() as connection:
                return connection.execute(text(statement)).scalar_one()
        finally:
            engine.dispose()

    def _table_sql(self) -> dict[str, str]:
        engine = create_engine(self.db_url)
        try:
            with engine.connect() as connection:
                rows = connection.execute(
                    text("SELECT name, sql FROM sqlite_master WHERE name IN ('links', 'blocked_links')")
                ).all()
            return {row[0]: row[1] for row in rows}
        finally:
            engine.dispose()

    def test_upgrade_adds_the_missing_foreign_keys_and_keeps_rows_and_indexes(self) -> None:
        self._drift_database()
        self.assertEqual(self._fk_columns("links"), set())
        self.assertEqual(self._fk_columns("blocked_links"), set())

        self._upgrade()

        self.assertEqual(self._fk_columns("links"), self.LINK_FKS)
        self.assertEqual(self._fk_columns("blocked_links"), self.BLOCKED_FKS)
        self.assertEqual(self._scalar("SELECT COUNT(*) FROM links"), 2)
        self.assertEqual(self._scalar("SELECT COUNT(*) FROM blocked_links"), 1)
        self.assertEqual(
            self._index_names("links"),
            {"ix_links_santa_id", "ix_links_receiver_id", "ix_links_group_id"},
        )
        self.assertEqual(
            self._index_names("blocked_links"),
            {
                "ix_blocked_links_participant_id",
                "ix_blocked_links_blocked_username",
                "ix_blocked_links_blocked_id",
            },
        )
        self.assertEqual(self._scalar("SELECT version_num FROM alembic_version"), self.HEAD)

    def test_downgrade_removes_only_the_constraints_this_revision_added(self) -> None:
        self._drift_database()
        self._upgrade()

        self._downgrade(self.PARENT)

        self.assertEqual(self._fk_columns("links"), set())
        self.assertEqual(self._fk_columns("blocked_links"), set())
        self.assertEqual(self._scalar("SELECT COUNT(*) FROM links"), 2)
        self.assertEqual(self._scalar("SELECT COUNT(*) FROM blocked_links"), 1)

        self._upgrade()
        self.assertEqual(self._fk_columns("links"), self.LINK_FKS)

    def test_existing_constraints_are_left_alone(self) -> None:
        """The patched baseline creates the FKs, so the revision must not rebuild the tables."""
        self._upgrade(self.PARENT)
        before = self._table_sql()

        self._upgrade()

        self.assertEqual(before, self._table_sql())
        self.assertEqual(self._fk_columns("links"), self.LINK_FKS)
        self.assertEqual(self._scalar("SELECT version_num FROM alembic_version"), self.HEAD)
