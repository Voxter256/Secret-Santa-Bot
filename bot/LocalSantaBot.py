import os.path

from configparser import ConfigParser
from telegram import Update
from telegram.ext import Updater

from bot.SantaBot import SantaBot


class LocalSantaBot(SantaBot):
    def __init__(self, dbConnection):
        super().__init__(dbConnection)
        self.read_config()
        try:
            self.bot_id = int(self.token.split(":")[0])
        except:
           self.bot_id = None

    def read_config(self):
        config = ConfigParser()
        configPath = os.path.normpath('config/config.ini')
        config.read(configPath)
        self.token = config.get('auth', 'token')
   
    def main(self):
        updater = Updater(self.token, use_context=True)

        dispatcher = updater.dispatcher
        for handler in self.handlers:
            dispatcher.add_handler(handler)

        updater.start_polling()
        print("running")
