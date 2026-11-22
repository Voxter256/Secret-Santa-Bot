from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from bot.Base import Base


class Participant(Base):
    __tablename__ = "participants"

    id: Mapped[int] = mapped_column(Integer(), primary_key=True)
    telegram_id: Mapped[int | None] = mapped_column(Integer, index=True)
    telegram_username: Mapped[str | None] = mapped_column(String(32), index=True)
    address: Mapped[str | None] = mapped_column(String(1028))
    created_at = Column(DateTime, server_default=func.now())
