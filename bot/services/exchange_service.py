from __future__ import annotations

import datetime
import uuid
from collections.abc import Callable

from bot.models.Link import Link
from bot.models.Participant import Participant
from bot.models.WishlistItem import WishlistItem
from bot.repositories.protocols import (
    BlockedLinkRepository,
    GroupRepository,
    LinkRepository,
    ParticipantRepository,
    WishlistRepository,
)
from bot.services.pairing_engine import PairingEngine, PairingResult

GettextFn = Callable[[str], str]

# Wishlist rules. MAX_TOTAL_LENGTH is the important one: the delivery message is
# capped by Telegram at 4096 characters, so a stored wishlist must stay well
# under that or items would be silently dropped at send time.
MAX_ITEMS = 20
MAX_ITEM_LENGTH = 1024
MAX_TOTAL_LENGTH = 3500


class ExchangeService:
    """Orchestrates exchange operations — between handlers and repositories."""

    def __init__(
        self,
        participants: ParticipantRepository,
        groups: GroupRepository,
        links: LinkRepository,
        blocked_links: BlockedLinkRepository,
        wishlists: WishlistRepository,
        pairing_engine: type[PairingEngine] = PairingEngine,
    ) -> None:
        self._participants = participants
        self._groups = groups
        self._links = links
        self._blocked_links = blocked_links
        self._wishlists = wishlists
        self._pairing = pairing_engine

    # ── Participant / address ──────────────────────────────────────────

    def find_or_create_participant(self, telegram_id: int, telegram_username: str | None) -> Participant:
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

    def participant_groups(self, participant_id: int):
        """Groups this participant has joined, oldest first."""
        return self._links.get_groups_by_santa(participant_id)

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

    def mark_group_left(self, chat_id: int) -> None:
        """Record that the bot lost access; data is kept for audit."""
        self._groups.set_left_at(chat_id, datetime.datetime.now(datetime.UTC).replace(tzinfo=None))

    def mark_group_active(self, chat_id: int) -> None:
        """Clear the flag if the bot is added back."""
        self._groups.set_left_at(chat_id, None)

    def group_is_orphaned(self, chat_id: int) -> bool:
        group = self._groups.get_by_telegram_id(chat_id)
        return bool(group is not None and group.left_at is not None)

    def group_options(self, chat_id: int) -> dict[str, bool]:
        group = self._groups.get_by_telegram_id(chat_id)
        if group is None:
            return {"requires_address": False, "wishlist_enabled": False}
        return {
            "requires_address": bool(group.requires_address),
            "wishlist_enabled": bool(group.wishlist_enabled),
        }

    # ── Wishlist ───────────────────────────────────────────────────────

    @staticmethod
    def render_wishlist(title: str, items: list[WishlistItem]) -> str:
        lines = [f"{position}. {item.details}" for position, item in enumerate(items, start=1)]
        return "\n".join([title, *lines])

    @staticmethod
    def _items_length(items: list[WishlistItem]) -> int:
        return sum(len(f"{position}. {item.details}") + 1 for position, item in enumerate(items, start=1))

    def add_wishlist_item(self, participant_id: int, chat_id: int, details: str) -> str:
        """Add an item, returning a status key the handler can translate."""
        text = details.strip()
        if not text:
            return "empty"
        if len(text) > MAX_ITEM_LENGTH:
            return "too_long"

        group = self._groups.get_by_telegram_id(chat_id)
        if group is None:
            return "no_group"
        if self._links.get_by_santa_and_group(participant_id, chat_id) is None:
            return "not_joined"
        if self._wishlists.count_for(group.id, participant_id) >= MAX_ITEMS:
            return "full"

        existing = self._wishlists.list_for(group.id, participant_id)
        next_line = len(f"{len(existing) + 1}. {text}") + 1
        if self._items_length(existing) + next_line > MAX_TOTAL_LENGTH:
            return "total_too_long"

        self._wishlists.add(group.id, participant_id, text)
        return "added"

    def list_wishlist_items(self, participant_id: int, chat_id: int) -> list[WishlistItem]:
        group = self._groups.get_by_telegram_id(chat_id)
        if group is None:
            return []
        return self._wishlists.list_for(group.id, participant_id)

    def remove_wishlist_item(self, participant_id: int, chat_id: int, position: int) -> bool:
        group = self._groups.get_by_telegram_id(chat_id)
        if group is None:
            return False
        items = self._wishlists.list_for(group.id, participant_id)
        if position < 1 or position > len(items):
            return False
        self._wishlists.delete(items[position - 1])
        return True

    def clear_wishlist(self, participant_id: int, chat_id: int) -> None:
        group = self._groups.get_by_telegram_id(chat_id)
        if group is None:
            return
        self._wishlists.clear(group.id, participant_id)

    def participants_without_wishlist(self, group_id: int, participant_ids: list[int]) -> list[Participant]:
        """Participants in this exchange with no wishlist items yet."""
        missing = [pid for pid in participant_ids if self._wishlists.count_for(group_id, pid) == 0]
        return [participant for participant in (self._participants.get_by_id(pid) for pid in missing) if participant]

    # ── Join / Leave ───────────────────────────────────────────────────

    def join_group(self, participant_id: int, chat_id: int, username: str | None) -> str:
        # Resolve any pending block referencing this username
        if username is not None:
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
        participants: list[int] = []
        # Collect all participant IDs in this group's exchange
        links = self._links.get_links_in_group(chat_id)
        for link in links:
            if link.santa_id is not None:
                participants.append(link.santa_id)

        if len(participants) < 2:
            return False, {}

        blocked_links = self._blocked_links.get_by_participant_ids(participants)
        # A pending block (username only, no resolved id) cannot constrain a pairing.
        blocked_pairings = [
            [bl.participant_id, bl.blocked_id]
            for bl in blocked_links
            if bl.participant_id is not None and bl.blocked_id is not None
        ]

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
