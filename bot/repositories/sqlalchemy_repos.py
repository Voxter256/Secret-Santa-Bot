from __future__ import annotations

import datetime

from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from bot.models.BlockedLink import BlockedLink
from bot.models.Feedback import Feedback
from bot.models.Group import Group
from bot.models.Link import Link
from bot.models.Participant import Participant
from bot.models.WishlistItem import WishlistItem


class SqlParticipantRepository:
    """SQLAlchemy implementation of ParticipantRepository."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_telegram_id(self, telegram_id: int) -> Participant | None:
        return self._session.scalars(select(Participant).where(Participant.telegram_id == telegram_id)).first()

    def get_by_id(self, participant_id: int) -> Participant | None:
        return self._session.get(Participant, participant_id)

    def get_by_username(self, username: str) -> Participant | None:
        return self._session.scalars(select(Participant).where(Participant.telegram_username == username)).first()

    def create(self, telegram_id: int, telegram_username: str) -> Participant:
        p = Participant(telegram_id=telegram_id, telegram_username=telegram_username)
        self._session.add(p)
        self._session.commit()
        return p

    def set_address(self, participant_id: int, address: str) -> None:
        p = self.get_by_id(participant_id)
        if p:
            p.address = address
            self._session.commit()


class SqlGroupRepository:
    """SQLAlchemy implementation of GroupRepository."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_telegram_id(self, chat_id: int) -> Group | None:
        return self._session.scalars(select(Group).where(Group.telegram_id == chat_id)).first()

    def create(self, telegram_id: int) -> Group:
        g = Group(telegram_id=telegram_id)
        self._session.add(g)
        self._session.commit()
        return g

    def _set(self, chat_id: int, **values: object) -> None:
        group = self.get_by_telegram_id(chat_id)
        if group is None:
            return
        for field, value in values.items():
            setattr(group, field, value)
        self._session.commit()

    def set_requires_address(self, chat_id: int, value: bool) -> None:
        self._set(chat_id, requires_address=value)

    def set_wishlist_enabled(self, chat_id: int, value: bool) -> None:
        self._set(chat_id, wishlist_enabled=value)

    def set_title(self, chat_id: int, title: str) -> None:
        self._set(chat_id, title=title)

    def set_left_at(self, chat_id: int, value: object) -> None:
        self._set(chat_id, left_at=value)


class SqlWishlistRepository:
    """SQLAlchemy implementation of WishlistRepository."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, group_id: int, participant_id: int, details: str) -> WishlistItem:
        item = WishlistItem(group_id=group_id, participant_id=participant_id, details=details)
        self._session.add(item)
        self._session.commit()
        return item

    def list_for(self, group_id: int, participant_id: int) -> list[WishlistItem]:
        stmt = (
            select(WishlistItem)
            .where(
                WishlistItem.group_id == group_id,
                WishlistItem.participant_id == participant_id,
            )
            .order_by(WishlistItem.id)
        )
        return list(self._session.scalars(stmt).all())

    def get(self, item_id: int) -> WishlistItem | None:
        return self._session.get(WishlistItem, item_id)

    def delete(self, item: WishlistItem) -> None:
        self._session.delete(item)
        self._session.commit()

    def clear(self, group_id: int, participant_id: int) -> None:
        self._session.execute(
            delete(WishlistItem).where(
                WishlistItem.group_id == group_id,
                WishlistItem.participant_id == participant_id,
            )
        )
        self._session.commit()

    def count_for(self, group_id: int, participant_id: int) -> int:
        stmt = (
            select(func.count())
            .select_from(WishlistItem)
            .where(
                WishlistItem.group_id == group_id,
                WishlistItem.participant_id == participant_id,
            )
        )
        return self._session.scalar(stmt) or 0

    def groups_with_items(self, participant_id: int) -> list[int]:
        stmt = select(WishlistItem.group_id).where(WishlistItem.participant_id == participant_id).distinct()
        return list(self._session.scalars(stmt).all())


class SqlLinkRepository:
    """SQLAlchemy implementation of LinkRepository."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_santa_and_group(self, santa_id: int, group_id: int) -> Link | None:
        stmt = select(Link).join(Group).where(Group.telegram_id == group_id, Link.santa_id == santa_id)
        return self._session.scalars(stmt).first()

    def get_first_in_group(self, group_id: int) -> Link | None:
        return self._session.scalars(select(Link).join(Group).where(Group.telegram_id == group_id)).first()

    def get_groups_by_santa(self, santa_id: int) -> list[Group]:
        """Every exchange this participant has joined, oldest first."""
        stmt = select(Group).join(Link, Link.group_id == Group.id).where(Link.santa_id == santa_id).order_by(Group.id)
        return list(self._session.scalars(stmt).all())

    def get_links_in_group(self, group_id: int) -> list[Link]:
        return list(self._session.scalars(select(Link).join(Group).where(Group.telegram_id == group_id)).all())

    def create(self, santa_id: int, group_id: int) -> Link:
        link = Link(santa_id=santa_id, group_id=group_id)
        self._session.add(link)
        self._session.commit()
        return link

    def delete(self, link: Link) -> None:
        self._session.delete(link)
        self._session.commit()

    def set_receiver(self, link: Link, receiver_id: int) -> None:
        link.receiver_id = receiver_id

    def set_pairing(self, group_id: int, pairing: dict[int, int]) -> None:
        """Persist the whole pairing in one transaction, before anything is sent."""
        now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
        for santa_id, receiver_id in pairing.items():
            link = self.get_by_santa_and_group(santa_id, group_id)
            if link is None:
                continue
            link.receiver_id = receiver_id
            link.assigned_at = now
            link.notified_at = None
        self._session.commit()

    def get_pending_notifications(self, group_id: int) -> list[Link]:
        stmt = (
            select(Link)
            .join(Group)
            .where(
                Group.telegram_id == group_id,
                Link.receiver_id.isnot(None),
                Link.notified_at.is_(None),
            )
        )
        return list(self._session.scalars(stmt).all())

    def mark_notified(self, link: Link) -> None:
        link.notified_at = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
        self._session.commit()

    def clear_receivers_in_group(self, group_id: int) -> None:
        links = self.get_links_in_group(group_id)
        for link in links:
            link.receiver_id = None
            link.assigned_at = None
            link.notified_at = None
        self._session.commit()


class SqlBlockedLinkRepository:
    """SQLAlchemy implementation of BlockedLinkRepository."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def find_by_blocker_and_username(self, blocker_id: int, username: str) -> BlockedLink | None:
        stmt = select(BlockedLink).where(
            BlockedLink.participant_id == blocker_id,
            BlockedLink.blocked_username == username,
        )
        return self._session.scalars(stmt).first()

    def find_by_ids(self, id_list: list[int]) -> BlockedLink | None:
        stmt = select(BlockedLink).where(
            BlockedLink.participant_id.in_(id_list),
            BlockedLink.blocked_id.in_(id_list),
        )
        return self._session.scalars(stmt).first()

    def create_by_username(self, participant_id: int, blocked_username: str) -> BlockedLink:
        bl = BlockedLink(participant_id=participant_id, blocked_username=blocked_username)
        self._session.add(bl)
        self._session.commit()
        return bl

    def create_by_id(self, participant_id: int, blocked_id: int) -> BlockedLink:
        bl = BlockedLink(participant_id=participant_id, blocked_id=blocked_id)
        self._session.add(bl)
        self._session.commit()
        return bl

    def find_for_allow(self, participant_id: int, username: str, blocked_id: int) -> BlockedLink | None:
        stmt = (
            select(BlockedLink)
            .join(BlockedLink.blocked, isouter=True)
            .where(
                BlockedLink.participant_id == participant_id,
                or_(
                    BlockedLink.blocked_username == username,
                    BlockedLink.blocked_id == blocked_id,
                ),
            )
        )
        return self._session.scalars(stmt).first()

    def delete(self, blocked_link: BlockedLink) -> None:
        self._session.delete(blocked_link)
        self._session.commit()

    def get_by_participant_ids(self, participant_ids: list[int]) -> list[BlockedLink]:
        stmt = select(BlockedLink).where(BlockedLink.participant_id.in_(participant_ids))
        return list(self._session.scalars(stmt).all())

    def resolve_pending_block(self, username: str, participant_id: int) -> None:
        bl = self._session.scalars(select(BlockedLink).where(BlockedLink.blocked_username == username)).first()
        if bl is not None:
            bl.blocked_id = participant_id
            bl.blocked_username = None
            self._session.commit()


class SqlFeedbackRepository:
    """SQLAlchemy implementation of FeedbackRepository."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(
        self,
        telegram_id: int,
        telegram_username: str | None,
        chat_id: int | None,
        body: str,
    ) -> Feedback:
        record = Feedback(
            telegram_id=telegram_id,
            telegram_username=telegram_username,
            chat_id=chat_id,
            body=body,
        )
        self._session.add(record)
        # Commit before forwarding so a failed Telegram send cannot lose the text.
        self._session.commit()
        return record

    def mark_forwarded(self, feedback_id: int) -> None:
        record = self._session.get(Feedback, feedback_id)
        if record is None:
            return
        record.forwarded_at = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
        self._session.commit()
