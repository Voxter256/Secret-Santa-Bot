from sqlalchemy import Column, Integer, ForeignKey
from sqlalchemy.orm import relationship, backref

from bot.Base import Base, Session

session = Session()


class Link(Base):
    __tablename__ = 'links'

    id = Column(Integer(), primary_key=True)
    santa_id = Column(Integer, ForeignKey('participants.id'), index=True)
    receiver_id = Column(Integer, ForeignKey('participants.id'), index=True, default=None)
    group_id = Column(Integer, ForeignKey('groups.id'), index=True)

    santa = relationship("Participant", uselist=False, backref=backref('link_santa'), foreign_keys=santa_id)
    receiver = relationship("Participant", uselist=False, backref=backref('link_receiver'), foreign_keys=receiver_id)
    groups = relationship("Group", uselist=False, backref=backref('links'))
