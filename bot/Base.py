from configparser import ConfigParser
from os.path import isfile, normpath
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, configure_mappers

# bot_database_file = "bot.sqlite"
# if not isfile(bot_database_file):
#     open(bot_database_file, 'w').close()


config = ConfigParser()
configPath = normpath('config/config.ini')
config.read(configPath)
url = config.get('db', 'url')
port = config.get('db', 'port')
username = config.get('db', 'username')
password = config.get('db', 'password')
databaseName = config.get('db', 'database_name')

dbConnectionString = "mysql+mysqlconnector://{}:{}@{}:{}/{}".format(username, password, url, port, databaseName)
engine = create_engine(dbConnectionString)
Session = sessionmaker(bind=engine)
Base = declarative_base()
configure_mappers()
