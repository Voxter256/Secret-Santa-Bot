import os
from os.path import isfile

from bot.DBConnection import DBConnection
from bot.LambdaSantaBot import LambdaSantaBot
from bot.LocalSantaBot import LocalSantaBot

if __name__ == "__main__":
    bot_database_file = "bot.sqlite"
    if not isfile(bot_database_file):
        open(bot_database_file, "w").close()
    dbConnectionString = "sqlite:///" + bot_database_file
    dbConnection = DBConnection(dbConnectionString)

    bot = LocalSantaBot(dbConnection)
    dbConnection.createAll()
    bot.main()


def lambda_handler(event, context):
    dbConnectionString = os.environ["DATABASE_URL"]
    dbConnection = DBConnection(dbConnectionString)

    bot = LambdaSantaBot(dbConnection)
    dbConnection.createAll()
    bot.process_message(event)

    return {
        "statusCode": 200,
    }
