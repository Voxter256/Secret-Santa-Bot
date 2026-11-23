from __future__ import annotations

import uuid
from typing import Callable

from bot.models.Link import Link
from bot.models.Participant import Participant
from bot.repositories.protocols import (
    BlockedLinkRepository,
    GroupRepository,
    LinkRepository,
    ParticipantRepository,
)
from bot.services.pairing_engine import PairingEngine, PairingResult

GettextFn = Callable[[str], str]


class ExchangeService:
    """Orchestrates exchange operations — between handlers and repositories."""

    def __init__(
        self,
        participants: ParticipantRepository,
        groups: GroupRepository,
        links: LinkRepository,
        blocked_links: BlockedLinkRepository,
        pairing_engine: type[PairingEngine] = PairingEngine,
    ) -> None:
        self._participants = participants
        self._groups = groups
        self._links = links
        self._blocked_links = blocked_links
        self._pairing = pairing_engine

    # ── Participant / address ──────────────────────────────────────────

    def find_or_create_participant(self, telegram_id: int, telegram_username: str) -> Participant:
        p = self._participants.get_by_telegram_id(telegram_id)
        if p is None:
            p = self._participants.create(telegram_id, telegram_username)
        return p

    def get_participant(self, telegram_id: int) -> Participant | None:
        return self._participants.get_by_telegram_id(telegram_id)

    def update_address(self, participant_id: int, address: str) -> None:
        self._participants.set_address(participant_id, address)

    # ── Group ──────────────────────────────────────────────────────────

    def find_or_create_group(self, chat_id: int):
        group = self._groups.get_by_telegram_id(chat_id)
        if group is None:
            group = self._groups.create(chat_id)
        return group

    def get_group(self, chat_id: int):
        return self._groups.get_by_telegram_id(chat_id)

    def set_group_option(
        self,
        chat_id: int,
        *,
        requires_address: bool | None = None,
        wishlist_enabled: bool | None = None,
    ) -> None:
        if requires_address is not None:
            self._groups.set_requires_address(chat_id, requires_address)
        if wishlist_enabled is not None:
            self._groups.set_wishlist_enabled(chat_id, wishlist_enabled)

    def set_group_title(self, chat_id: int, title: str) -> None:
        self._groups.set_title(chat_id, title)

    def group_options(self, chat_id: int) -> dict[str, bool]:
        group = self._groups.get_by_telegram_id(chat_id)
        if group is None:
            return {"requires_address": False, "wishlist_enabled": False}
        return {
            "requires_address": bool(group.requires_address),
            "wishlist_enabled": bool(group.wishlist_enabled),
        }

    # ── Join / Leave ───────────────────────────────────────────────────

    def join_group(self, participant_id: int, chat_id: int, username: str) -> str:
        # Resolve any pending block referencing this username
        self._blocked_links.resolve_pending_block(username, participant_id)

        existing = self._links.get_by_santa_and_group(participant_id, chat_id)
        if existing is not None:
            return "already_joined"

        group = self._groups.get_by_telegram_id(chat_id)
        if group is None:
            return "no_group"
        self._links.create(participant_id, group.id)
        return "joined"

    def leave_group(self, participant_id: int, chat_id: int) -> str:
        link = self._links.get_by_santa_and_group(participant_id, chat_id)
        if link is None:
            return "not_joined"
        self._links.delete(link)
        return "left"

    # ── Blocking ───────────────────────────────────────────────────────

    def block_by_username(self, blocker_id: int, username: str) -> str:
        target = self._participants.get_by_username(username)
        if target is None:
            existing = self._blocked_links.find_by_blocker_and_username(blocker_id, username)
            if existing is not None:
                return "already_blocked"
            self._blocked_links.create_by_username(blocker_id, username)
            return "blocked"

        if target.id == blocker_id:
            return "self_block"

        id_list = [blocker_id, target.id]
        existing = self._blocked_links.find_by_ids(id_list)
        if existing is not None:
            return "already_blocked"
        self._blocked_links.create_by_id(blocker_id, target.id)
        return "blocked"

    def block_by_user_id(self, blocker_id: int, mentioned_id: int) -> str:
        target = self._participants.get_by_telegram_id(mentioned_id)
        if target is None:
            return "needs_join_first"
        id_list = [blocker_id, target.id]
        existing = self._blocked_links.find_by_ids(id_list)
        if existing is not None:
            return "already_blocked"
        self._blocked_links.create_by_id(blocker_id, target.id)
        return "blocked"

    def unblock(self, blocker_id: int, username: str, mentioned_id: int) -> bool:
        bl = self._blocked_links.find_for_allow(blocker_id, username, mentioned_id)
        if bl is None:
            return False
        self._blocked_links.delete(bl)
        return True

    # ── Exchange ───────────────────────────────────────────────────────

    def get_exchange_status(self, chat_id: int) -> tuple[str, list[Link]]:
        """Returns (status_label, links_list)."""
        group = self._groups.get_by_telegram_id(chat_id)
        if group is None:
            return "no_group", []

        link = self._links.get_first_in_group(chat_id)
        if link is None or link.receiver_id is None:
            return "not_begun", list(group.links)
        if self._links.get_pending_notifications(chat_id):
            return "delivery_pending", list(group.links)
        return "finished", list(group.links)

    def is_exchange_setup(self, chat_id: int) -> str | None:
        """Returns None if exchange can proceed, or an error message key."""
        link = self._links.get_first_in_group(chat_id)
        if link is None:
            return "no_joins"
        if link.receiver_id is not None:
            return "already_setup"
        return None

    def run_exchange(self, chat_id: int) -> PairingResult:
        participants = []
        # Collect all participant IDs in this group's exchange
        links = self._links.get_links_in_group(chat_id)
        for link in links:
            participants.append(link.santa_id)

        if len(participants) < 2:
            return False, {}

        blocked_links = self._blocked_links.get_by_participant_ids(participants)
        blocked_pairings = [[bl.participant_id, bl.blocked_id] for bl in blocked_links]

        return self._pairing.find_combination(participants, blocked_pairings)

    def assign_receiver(self, chat_id: int, santa_id: int, receiver_id: int) -> None:
        link = self._links.get_by_santa_and_group(santa_id, chat_id)
        if link:
            self._links.set_receiver(link, receiver_id)

    def assign_pairing(self, chat_id: int, pairing: dict[int, int]) -> None:
        """Persist the whole pairing atomically, before delivery is attempted."""
        self._links.set_pairing(chat_id, pairing)

    def pending_deliveries(self, chat_id: int) -> list[Link]:
        return self._links.get_pending_notifications(chat_id)

    def mark_delivered(self, link: Link) -> None:
        self._links.mark_notified(link)

    def reset_exchange(self, chat_id: int) -> None:
        self._links.clear_receivers_in_group(chat_id)

    # ── Error handling ─────────────────────────────────────────────────

    @staticmethod
    def format_exception_id() -> str:
        return str(uuid.uuid4())
