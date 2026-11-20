from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.orm import backref, relationship

from bot.Base import Base


class BlockedLink(Base):
    __tablename__ = "blocked_links"

    id = Column(Integer(), primary_key=True)
    participant_id = Column(Integer, ForeignKey("participants.id"), index=True)
    blocked_username = Column(String(32), index=True, nullable=True)
    blocked_id = Column(
        Integer,
        ForeignKey("participants.id"),
        index=True,
        nullable=True,
    )

    blocker = relationship("Participant", uselist=False, backref=backref("blocker_link"), foreign_keys=participant_id)
    blocked = relationship("Participant", uselist=False, backref=backref("blocked_link"), foreign_keys=blocked_id)
