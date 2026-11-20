import os

from telegram import Bot, Update
from telegram.ext import Application

from bot.SantaBot import SantaBot


class LambdaSantaBot(SantaBot):
    def __init__(self, dbConnection):
        super().__init__(dbConnection)
        self.token = os.environ['TELEGRAM_BOT_TOKEN']
        try:
            self.bot_id = int(self.token.split(":")[0])
        except Exception:
            self.bot_id = None

        self.bot = Bot(self.token)
        self.application = (
            Application.builder()
            .bot(self.bot)
            .build()
        )

        for handler in self.handlers:
            self.application.add_handler(handler)

    def process_message(self, updateText):
        print('incoming message')
        print(updateText)
        decodedUpdate = Update.de_json(updateText, self.bot)
        self.application.process_update(decodedUpdate)
        self.session.close()