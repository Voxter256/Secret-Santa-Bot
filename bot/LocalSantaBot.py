import logging
import os

from telegram.ext import Application

from bot.SantaBot import SantaBot


class LocalSantaBot(SantaBot):
    def __init__(self, dbConnection):
        super().__init__(dbConnection)

        formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
        handler = logging.FileHandler(filename="santabot.log", encoding="utf-8")
        handler.setFormatter(formatter)
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
