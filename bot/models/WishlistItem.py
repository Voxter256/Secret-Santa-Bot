import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, backref, mapped_column, relationship
from sqlalchemy.sql import func

from bot.Base import Base


class WishlistItem(Base):
    __tablename__ = "wishlist_items"
    __table_args__ = (Index("ix_wishlist_items_group_participant", "group_id", "participant_id"),)

    id: Mapped[int] = mapped_column(Integer(), primary_key=True)
    group_id: Mapped[int] = mapped_column(Integer, ForeignKey("groups.id"), nullable=False)
    participant_id: Mapped[int] = mapped_column(Integer, ForeignKey("participants.id"), nullable=False)
    details: Mapped[str] = mapped_column(String(2048), nullable=False)
    created_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, server_default=func.now())

    participant = relationship(
        "Participant",
        uselist=False,
        backref=backref("wishlist_items"),
        foreign_keys=participant_id,
    )
    group = relationship(
        "Group",
        uselist=False,
        backref=backref("wishlist_items"),
        foreign_keys=group_id,
    )
