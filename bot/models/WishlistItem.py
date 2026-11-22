from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, backref, mapped_column, relationship

from bot.Base import Base


class WishlistItem(Base):
    __tablename__ = "wishlist_items"

    id: Mapped[int] = mapped_column(Integer(), primary_key=True)
    participant_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("participants.id"), index=True)
    details: Mapped[str | None] = mapped_column(String(2048))

    participant = relationship(
        "Participant",
        uselist=False,
        backref=backref("wishlist_items"),
        foreign_keys=participant_id,
    )
