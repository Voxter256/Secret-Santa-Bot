import datetime

from sqlalchemy import DateTime, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from bot.Base import Base
from bot.models.Group import Group
from bot.models.Participant import Participant


class Link(Base):
    __tablename__ = "links"

    id: Mapped[int] = mapped_column(Integer(), primary_key=True)
    santa_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("participants.id"), index=True)
    receiver_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("participants.id"), index=True, default=None)
    group_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("groups.id"), index=True)
    created_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, server_default=func.now())
    assigned_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)
    notified_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)

    santa: Mapped[Participant | None] = relationship(back_populates="link_santa", foreign_keys=santa_id)
    receiver: Mapped[Participant | None] = relationship(back_populates="link_receiver", foreign_keys=receiver_id)
    groups: Mapped[Group | None] = relationship(back_populates="links")
