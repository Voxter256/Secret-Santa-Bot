import logging
import os.path

from configparser import ConfigParser
from telegram.ext import Updater

from bot.SantaBot import SantaBot
from bot.overrides.network_loop_retry_override import _network_loop_retry


class LocalSantaBot(SantaBot):
    def __init__(self, dbConnection):
        super().__init__(dbConnection)

        formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
        handler = logging.FileHandler(
            filename='santabot.log', encoding='utf-8'
        )
        handler.setFormatter(formatter)
        logger = logging.getLogger()
        logger.setLevel(logging.INFO)
        logger.addHandler(handler)

        self.read_config()
        try:
            self.bot_id = int(self.token.split(":")[0])
        except Exception:
            self.bot_id = None

    def read_config(self):
        config = ConfigParser()
        configPath = os.path.normpath('config/config.ini')
        config.read(configPath)
        self.token = config.get('auth', 'token')

    def main(self):
        Updater._network_loop_retry = _network_loop_retry
        updater = Updater(self.token, use_context=True)

        dispatcher = updater.dispatcher
        for handler in self.handlers:
            dispatcher.add_handler(handler)

        updater.start_polling()
        print("running")
