from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, Text
from sqlalchemy.orm import backref, relationship
from sqlalchemy.sql import func

from bot.Base import Base


class ExchangeEvent(Base):
    __tablename__ = "exchange_events"

    id = Column(Integer(), primary_key=True)
    group_id = Column(Integer, ForeignKey("groups.id"), index=True, nullable=False)
    timestamp = Column(DateTime, server_default=func.now(), nullable=False)
    success = Column(Boolean, nullable=False)
    attempt_data = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0, nullable=False)

    group = relationship("Group", uselist=False, backref=backref("exchange_events"), foreign_keys=group_id)