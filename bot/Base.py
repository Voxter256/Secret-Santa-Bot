from os.path import isfile
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, configure_mappers

bot_database_file = "bot.sqlite"
if not isfile(bot_database_file):
    open(bot_database_file, 'w').close()
engine = create_engine('sqlite:///' + bot_database_file)
Session = sessionmaker(bind=engine)
Base = declarative_base()
configure_mappers()
