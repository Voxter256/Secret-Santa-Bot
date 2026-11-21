from sqlalchemy import create_engine
from sqlalchemy.orm import configure_mappers, sessionmaker
from sqlalchemy.pool import StaticPool

IN_MEMORY_URLS = {"sqlite://", "sqlite:///:memory:"}


class DBConnection:
    def __init__(self, connectionString):
        if connectionString in IN_MEMORY_URLS:
            # Every connection to an in-memory SQLite database gets its own
            # private copy, so hold a single connection for the whole engine.
            self.engine = create_engine(
                connectionString,
                poolclass=StaticPool,
                connect_args={"check_same_thread": False},
            )
        else:
            self.engine = create_engine(connectionString)
        sessionMaker = sessionmaker(bind=self.engine)
        self.session = sessionMaker()

        configure_mappers()
