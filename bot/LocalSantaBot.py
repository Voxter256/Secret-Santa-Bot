import logging
import logging.handlers
import os

from telegram.ext import Application

from bot.log_context import CorrelationFilter
from bot.SantaBot import SantaBot


class PrivateRotatingFileHandler(logging.handlers.TimedRotatingFileHandler):
    """Rotating handler that keeps the log readable only by its owner.

    ``FileHandler`` creates the file with the process umask (0644 on most systems),
    and ``doRollover`` recreates the active file the same way, so the mode has to be
    re-applied on every open rather than once at startup. A rotated file keeps the
    inode it was renamed from, so it inherits whatever mode the active file had.
    """

    FILE_MODE = 0o600

    def _open(self):
        stream = super()._open()
        self._restrict()
        return stream

    def _restrict(self) -> None:
        try:
            os.chmod(self.baseFilename, self.FILE_MODE)
        except OSError as this_ex:
            # Losing log privacy is worth a warning, not a crash.
            logging.getLogger(__name__).warning(f"Could not restrict {self.baseFilename} to 0600: {this_ex}")


def build_log_handler(filename: str = "santabot.log") -> logging.handlers.TimedRotatingFileHandler:
    """Weekly rotation, 52 files kept — about a year of history.

    Rotation happens when a record is written, not on a timer, so an idle
    bot keeps its last file until it next logs. 52 slots is therefore a
    count of files, not a strict 12-month cutoff.
    """
    return PrivateRotatingFileHandler(
        filename,
        when="W0",
        interval=1,
        backupCount=52,
        encoding="utf-8",
    )


class LocalSantaBot(SantaBot):
    def __init__(self, dbConnection):
        super().__init__(dbConnection)

        formatter = logging.Formatter("%(asctime)s %(levelname)s [%(correlation_id)s] %(message)s")
        handler = build_log_handler()
        handler.setFormatter(formatter)
        handler.addFilter(CorrelationFilter())
        logger = logging.getLogger()
        logger.setLevel(logging.INFO)
        logger.addHandler(handler)

        self.token = os.environ["TELEGRAM_BOT_TOKEN"]
        try:
            self.bot_id = int(self.token.split(":")[0])
        except Exception:
            self.bot_id = None

    def main(self):
        application = Application.builder().token(self.token).build()
        for observer in self.update_middleware:
            application.add_handler(observer, group=-1)
        for handler in self.handlers:
            application.add_handler(handler)

        # One line that makes a stale or duplicate instance obvious: the pid
        # and the exact log file this process holds open. A renamed log file
        # keeps receiving writes from the process that already has it open, so
        # "no log output" can otherwise mean "wrong file", not "not running".
        log_file = next((h.baseFilename for h in logging.getLogger().handlers if hasattr(h, "baseFilename")), None)
        logging.info(f"SantaBot starting | pid {os.getpid()} | bot id {self.bot_id} | logging to {log_file}")

        application.run_polling()
        print("running")
