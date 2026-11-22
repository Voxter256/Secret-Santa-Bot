from sqlalchemy import Column, DateTime, Integer
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from bot.Base import Base


class Group(Base):
    __tablename__ = "groups"

    id: Mapped[int] = mapped_column(Integer(), primary_key=True)
    telegram_id: Mapped[int | None] = mapped_column(Integer)
    created_at = Column(DateTime, server_default=func.now())
