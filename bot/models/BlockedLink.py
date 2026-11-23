from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.Base import Base
from bot.models.Participant import Participant


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

    blocker: Mapped[Participant | None] = relationship(back_populates="blocker_link", foreign_keys=participant_id)
    blocked: Mapped[Participant | None] = relationship(back_populates="blocked_link", foreign_keys=blocked_id)
