from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, configure_mappers

from bot.Base import Base


class DBConnection():

    def __init__(self, connectionString):
        self.engine = create_engine(connectionString)
        sessionMaker = sessionmaker(bind=self.engine)
        self.session = sessionMaker()

        configure_mappers()

    def createAll(self):
        Base.metadata.create_all(self.engine)

    def dropAll(self):
        Base.metadata.drop_all(self.engine)
