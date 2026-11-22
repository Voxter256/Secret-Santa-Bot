import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, backref, mapped_column, relationship
from sqlalchemy.sql import func

from bot.Base import Base


class ExchangeEvent(Base):
    __tablename__ = "exchange_events"

    id: Mapped[int] = mapped_column(Integer(), primary_key=True)
    group_id: Mapped[int] = mapped_column(Integer, ForeignKey("groups.id"), index=True, nullable=False)
    timestamp: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    attempt_data: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    group = relationship("Group", uselist=False, backref=backref("exchange_events"), foreign_keys=group_id)
