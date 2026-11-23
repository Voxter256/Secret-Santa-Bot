import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from bot.Base import Base

if TYPE_CHECKING:
    from bot.models.ExchangeEvent import ExchangeEvent
    from bot.models.Link import Link
    from bot.models.WishlistItem import WishlistItem


class Group(Base):
    __tablename__ = "groups"

    id: Mapped[int] = mapped_column(Integer(), primary_key=True)
    telegram_id: Mapped[int | None] = mapped_column(Integer)
    title: Mapped[str | None] = mapped_column(String(255))
    requires_address: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("0"))
    wishlist_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("0"))
    left_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, server_default=func.now())

    links: Mapped[list["Link"]] = relationship(back_populates="groups")
    wishlist_items: Mapped[list["WishlistItem"]] = relationship(back_populates="group")
    exchange_events: Mapped[list["ExchangeEvent"]] = relationship(back_populates="group")
