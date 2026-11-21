from sqlalchemy import Column, DateTime, Integer
from sqlalchemy.sql import func

from bot.Base import Base


class Group(Base):
    __tablename__ = "groups"

    id = Column(Integer(), primary_key=True)
    telegram_id = Column(Integer)
    created_at = Column(DateTime, server_default=func.now())
