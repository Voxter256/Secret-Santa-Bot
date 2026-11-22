import os
from os.path import isfile

from bot._migrate import run_migrations
from bot.DBConnection import DBConnection
from bot.LambdaSantaBot import LambdaSantaBot
from bot.LocalSantaBot import LocalSantaBot

if __name__ == "__main__":
    bot_database_file = "bot.sqlite"
    if not isfile(bot_database_file):
        open(bot_database_file, "w").close()
    dbConnectionString = "sqlite:///" + bot_database_file
    run_migrations(dbConnectionString)
    dbConnection = DBConnection(dbConnectionString)

    bot = LocalSantaBot(dbConnection)
    bot.main()


def lambda_handler(event, context):
    dbConnectionString = os.environ["DATABASE_URL"]
    run_migrations(dbConnectionString)
    dbConnection = DBConnection(dbConnectionString)

    bot = LambdaSantaBot(dbConnection)
    bot.process_message(event)

    return {
        "statusCode": 200,
    }
