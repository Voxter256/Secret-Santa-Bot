from bot.LambdaSantaBot import LambdaSantaBot
from bot.LocalSantaBot import LocalSantaBot
from bot.DBConnection import DBConnection
from configparser import ConfigParser
from os.path import isfile, normpath


if __name__ == '__main__':

    bot_database_file = "bot.sqlite"
    if not isfile(bot_database_file):
        open(bot_database_file, 'w').close()
    dbConnectionString = 'sqlite:///' + bot_database_file
    dbConnection = DBConnection(dbConnectionString)

    bot = LocalSantaBot(dbConnection)
    dbConnection.createAll()
    bot.main()


def lambda_handler(event, context):

    config = ConfigParser()
    configPath = normpath('config/config.ini')
    config.read(configPath)
    url = config.get('db', 'url')
    port = config.get('db', 'port')
    username = config.get('db', 'username')
    password = config.get('db', 'password')
    databaseName = config.get('db', 'database_name')
    dbConnectionString = (
        f"mysql+mysqlconnector://"
        f"{username}:{password}"
        f"@{url}:{port}/{databaseName}"
    )

    dbConnection = DBConnection(dbConnectionString)

    bot = LambdaSantaBot(dbConnection)
    dbConnection.createAll()
    bot.process_message(event)

    return {
        'statusCode': 200,
    }
