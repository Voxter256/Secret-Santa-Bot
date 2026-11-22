from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, backref, mapped_column, relationship

from bot.Base import Base


class BlockedLink(Base):
    __tablename__ = "blocked_links"

    id: Mapped[int] = mapped_column(Integer(), primary_key=True)
    participant_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("participants.id"), index=True)
    blocked_username: Mapped[str | None] = mapped_column(String(32), index=True, nullable=True)
    blocked_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("participants.id"),
        index=True,
        nullable=True,
    )

    blocker = relationship("Participant", uselist=False, backref=backref("blocker_link"), foreign_keys=participant_id)
    blocked = relationship("Participant", uselist=False, backref=backref("blocked_link"), foreign_keys=blocked_id)
