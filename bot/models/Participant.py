import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from bot.Base import Base

if TYPE_CHECKING:
    from bot.models.BlockedLink import BlockedLink
    from bot.models.Link import Link
    from bot.models.WishlistItem import WishlistItem


class Participant(Base):
    __tablename__ = "participants"

    id: Mapped[int] = mapped_column(Integer(), primary_key=True)
    telegram_id: Mapped[int | None] = mapped_column(Integer, index=True)
    telegram_username: Mapped[str | None] = mapped_column(String(32), index=True)
    address: Mapped[str | None] = mapped_column(String(1028))
    created_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, server_default=func.now())

    # Reverse sides of the Link / BlockedLink / WishlistItem relationships.
    # Each of those tables has two FKs to participants, so the FK must be named.
    link_santa: Mapped[list["Link"]] = relationship(back_populates="santa", foreign_keys="Link.santa_id")
    link_receiver: Mapped[list["Link"]] = relationship(back_populates="receiver", foreign_keys="Link.receiver_id")
    blocker_link: Mapped[list["BlockedLink"]] = relationship(
        back_populates="blocker", foreign_keys="BlockedLink.participant_id"
    )
    blocked_link: Mapped[list["BlockedLink"]] = relationship(
        back_populates="blocked", foreign_keys="BlockedLink.blocked_id"
    )
    wishlist_items: Mapped[list["WishlistItem"]] = relationship(back_populates="participant")
