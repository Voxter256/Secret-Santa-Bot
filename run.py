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
    # The database holds mailing addresses; keep it owner-only.
    try:
        os.chmod(bot_database_file, 0o600)
    except OSError as this_ex:
        print(f"warning: could not restrict {bot_database_file} to 0600: {this_ex}")
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
