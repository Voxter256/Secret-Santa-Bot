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
