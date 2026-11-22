from sqlalchemy import Column, DateTime, ForeignKey, Integer
from sqlalchemy.orm import backref, relationship
from sqlalchemy.sql import func

from bot.Base import Base


class Link(Base):
    __tablename__ = "links"

    id = Column(Integer(), primary_key=True)
    santa_id = Column(Integer, ForeignKey("participants.id"), index=True)
    receiver_id = Column(Integer, ForeignKey("participants.id"), index=True, default=None)
    group_id = Column(Integer, ForeignKey("groups.id"), index=True)
    created_at = Column(DateTime, server_default=func.now())
    assigned_at = Column(DateTime, nullable=True)
    notified_at = Column(DateTime, nullable=True)

    santa = relationship("Participant", uselist=False, backref=backref("link_santa"), foreign_keys=santa_id)
    receiver = relationship("Participant", uselist=False, backref=backref("link_receiver"), foreign_keys=receiver_id)
    groups = relationship("Group", uselist=False, backref=backref("links"))
