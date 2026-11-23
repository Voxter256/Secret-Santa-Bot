import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from bot.Base import Base


class Feedback(Base):
    """One free-text message a user sent with /feedback.

    The row is the durable copy: forwarding to the owner's chat is best-effort,
    and ``forwarded_at`` records whether the send worked. A feedback row with a
    NULL ``forwarded_at`` is therefore readable from the database even when
    Telegram delivery failed.
    """

    __tablename__ = "feedback"

    id: Mapped[int] = mapped_column(Integer(), primary_key=True)
    telegram_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    telegram_username: Mapped[str | None] = mapped_column(String(32), nullable=True)
    chat_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, server_default=func.now())
    forwarded_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)
