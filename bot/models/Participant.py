from sqlalchemy import Column, Integer, String

from bot.Base import Base


class Participant(Base):
    __tablename__ = 'participants'

    id = Column(Integer(), primary_key=True)
    telegram_id = Column(Integer, index=True)
    telegram_username = Column(String(32), index=True)
    address = Column(String(1028))
