import os.path

from configparser import ConfigParser
from telegram import Bot, Update
from telegram.ext import Dispatcher

from bot.SantaBot import SantaBot


class LambdaSantaBot(SantaBot):
    def __init__(self, dbConnection):
        super().__init__(dbConnection)
        self.read_config()  # TODO Replace with Environment Variables
        try:
            self.bot_id = int(self.token.split(":")[0])
        except Exception:
            self.bot_id = None

        self.bot = Bot(self.token)
        self.dispatcher = Dispatcher(
            self.bot, None, workers=0, use_context=True)

        for handler in self.handlers:
            self.dispatcher.add_handler(handler)

    def read_config(self):  # TODO Replace with Environment Variables
        config = ConfigParser()
        configPath = os.path.normpath('config/config.ini')
        config.read(configPath)
        self.token = config.get('auth', 'token')

    def process_message(self, updateText):
        print('incoming message')
        print(updateText)
        decodedUpdate = Update.de_json(updateText, self.bot)
        self.dispatcher.process_update(decodedUpdate)
        self.session.close()
