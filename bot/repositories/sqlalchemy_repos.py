from __future__ import annotations

import datetime

from sqlalchemy import or_
from sqlalchemy.orm import Session

from bot.models.BlockedLink import BlockedLink
from bot.models.Group import Group
from bot.models.Link import Link
from bot.models.Participant import Participant


class SqlParticipantRepository:
    """SQLAlchemy implementation of ParticipantRepository."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_telegram_id(self, telegram_id: int) -> Participant | None:
        return self._session.query(Participant).filter(Participant.telegram_id == telegram_id).first()

    def get_by_id(self, participant_id: int) -> Participant | None:
        return self._session.query(Participant).get(participant_id)

    def get_by_username(self, username: str) -> Participant | None:
        return self._session.query(Participant).filter(Participant.telegram_username == username).first()

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
        return self._session.query(Group).filter(Group.telegram_id == chat_id).first()

    def create(self, telegram_id: int) -> Group:
        g = Group(telegram_id=telegram_id)
        self._session.add(g)
        self._session.commit()
        return g


class SqlLinkRepository:
    """SQLAlchemy implementation of LinkRepository."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_santa_and_group(self, santa_id: int, group_id: int) -> Link | None:
        return (
            self._session.query(Link)
            .join(Group)
            .filter(Group.telegram_id == group_id, Link.santa_id == santa_id)
            .first()
        )

    def get_first_in_group(self, group_id: int) -> Link | None:
        return self._session.query(Link).join(Group).filter(Group.telegram_id == group_id).first()

    def get_links_in_group(self, group_id: int) -> list[Link]:
        return self._session.query(Link).join(Group).filter(Group.telegram_id == group_id).all()

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
        return (
            self._session.query(Link)
            .join(Group)
            .filter(
                Group.telegram_id == group_id,
                Link.receiver_id.isnot(None),
                Link.notified_at.is_(None),
            )
            .all()
        )

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
        return (
            self._session.query(BlockedLink)
            .filter(
                BlockedLink.participant_id == blocker_id,
                BlockedLink.blocked_username == username,
            )
            .first()
        )

    def find_by_ids(self, id_list: list[int]) -> BlockedLink | None:
        return (
            self._session.query(BlockedLink)
            .filter(
                BlockedLink.participant_id.in_(id_list),
                BlockedLink.blocked_id.in_(id_list),
            )
            .first()
        )

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
        return (
            self._session.query(BlockedLink)
            .join(BlockedLink.blocked, isouter=True)
            .filter(BlockedLink.participant_id == participant_id)
            .filter(
                or_(
                    BlockedLink.blocked_username == username,
                    BlockedLink.blocked_id == blocked_id,
                )
            )
            .first()
        )

    def delete(self, blocked_link: BlockedLink) -> None:
        self._session.delete(blocked_link)
        self._session.commit()

    def get_by_participant_ids(self, participant_ids: list[int]) -> list[BlockedLink]:
        return self._session.query(BlockedLink).filter(BlockedLink.participant_id.in_(participant_ids)).all()

    def resolve_pending_block(self, username: str, participant_id: int) -> None:
        bl = self._session.query(BlockedLink).filter(BlockedLink.blocked_username == username).first()
        if bl is not None:
            bl.blocked_id = participant_id
            bl.blocked_username = None
            self._session.commit()
