import datetime
import logging.handlers
import os
import pathlib
import tempfile
import unittest
from unittest.mock import patch

from bot.DBConnection import DBConnection
from bot.LocalSantaBot import LocalSantaBot, build_log_handler


class TestLogRotation(unittest.TestCase):
    """Seasonal project: one year of weekly files, then the oldest is dropped."""

    def test_handler_rotates_weekly_and_keeps_52_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = pathlib.Path(tmpdir) / "santabot.log"
            handler = build_log_handler(str(path))
            self.addCleanup(handler.close)

            self.assertIsInstance(handler, logging.handlers.TimedRotatingFileHandler)  # narrows at runtime
            self.assertEqual(handler.when, "W0")
            self.assertEqual(handler.backupCount, 52)
            self.assertEqual(handler.interval, datetime.timedelta(days=7).total_seconds())
            self.assertEqual(pathlib.Path(handler.baseFilename), path)

    @staticmethod
    def _record(message: str = "hello") -> logging.LogRecord:
        return logging.LogRecord("test", logging.INFO, __file__, 1, message, None, None)

    def test_log_file_is_created_owner_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = pathlib.Path(tmpdir) / "santabot.log"
            handler = build_log_handler(str(path))
            self.addCleanup(handler.close)

            self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_rotated_files_are_owner_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = pathlib.Path(tmpdir) / "santabot.log"
            handler = build_log_handler(str(path))
            self.addCleanup(handler.close)
            handler.handle(self._record())

            handler.doRollover()

            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            rotated = [entry for entry in pathlib.Path(tmpdir).iterdir() if entry != path]
            self.assertEqual(len(rotated), 1, rotated)
            self.assertEqual(rotated[0].stat().st_mode & 0o777, 0o600)

    def test_an_existing_world_readable_log_is_tightened(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = pathlib.Path(tmpdir) / "santabot.log"
            path.write_text("2022-01-01 old entry\n", encoding="utf-8")
            os.chmod(path, 0o644)

            handler = build_log_handler(str(path))
            self.addCleanup(handler.close)

            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertIn("old entry", path.read_text(encoding="utf-8"))

    def test_local_bot_uses_the_rotating_handler(self) -> None:
        db = DBConnection("sqlite://")
        self.addCleanup(db.engine.dispose)

        root = logging.getLogger()
        before = set(root.handlers)
        # A real handler, not a Mock: a Mock attached to the root logger raises
        # TypeError in Logger.callHandlers (int >= Mock) the next time anything logs.
        with (
            patch("bot.LocalSantaBot.build_log_handler", return_value=logging.NullHandler()) as factory,
            patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "123:abc"}),
        ):
            LocalSantaBot(db)
        for handler in set(root.handlers) - before:
            root.removeHandler(handler)
        factory.assert_called_once_with()
