from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship, backref

from bot.Base import Base, Session

session = Session()


class BlockedLink(Base):
    __tablename__ = 'blocked_links'

    id = Column(Integer(), primary_key=True)
    participant_id = Column(Integer, ForeignKey('participants.id'), index=True)
    blocked_username = Column(String, index=True, nullable=True)
    blocked_id = Column(Integer, ForeignKey('participants.id'), index=True, nullable=True)

    blocker = relationship("Participant", uselist=False, backref=backref('blocker_link'), foreign_keys=participant_id)
    blocked = relationship("Participant", uselist=False, backref=backref('blocked_link'), foreign_keys=blocked_id)
