from sqlalchemy import Boolean, Column, DateTime, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from bot.Base import Base


class Group(Base):
    __tablename__ = "groups"

    id: Mapped[int] = mapped_column(Integer(), primary_key=True)
    telegram_id: Mapped[int | None] = mapped_column(Integer)
    title: Mapped[str | None] = mapped_column(String(255))
    requires_address: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("0"))
    wishlist_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("0"))
    created_at = Column(DateTime, server_default=func.now())
