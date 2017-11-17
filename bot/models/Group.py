from sqlalchemy import Column, Integer

from bot.Base import Base, Session

session = Session()


class Group(Base):
    __tablename__ = 'groups'

    id = Column(Integer(), primary_key=True)
    telegram_id = Column(Integer)
