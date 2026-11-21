from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.orm import backref, relationship

from bot.Base import Base


class WishlistItem(Base):
    __tablename__ = "wishlist_items"

    id = Column(Integer(), primary_key=True)
    participant_id = Column(
        Integer, ForeignKey("participants.id"), index=True
    )
    details = Column(String(2048))

    participant = relationship(
        "Participant",
        uselist=False,
        backref=backref("wishlist_items"),
        foreign_keys=participant_id,
    )