import unittest
from unittest.mock import MagicMock

from bot.services.exchange_service import ExchangeService


class TestExchangeService(unittest.TestCase):
    """Tests for ExchangeService using mock repositories — no SQLAlchemy."""

    def setUp(self):
        self.participants = MagicMock()
        self.groups = MagicMock()
        self.links = MagicMock()
        self.blocked_links = MagicMock()
        self.wishlists = MagicMock()
        self.service = ExchangeService(
            participants=self.participants,
            groups=self.groups,
            links=self.links,
            blocked_links=self.blocked_links,
            wishlists=self.wishlists,
        )

    # ── Participant ────────────────────────────────────────────────────

    def test_find_or_create_participant_exists(self):
        mock_p = MagicMock()
        self.participants.get_by_telegram_id.return_value = mock_p
        result = self.service.find_or_create_participant(10, "TestUser")
        self.assertIs(result, mock_p)
        self.participants.create.assert_not_called()

    def test_find_or_create_participant_new(self):
        self.participants.get_by_telegram_id.return_value = None
        mock_p = MagicMock()
        self.participants.create.return_value = mock_p
        result = self.service.find_or_create_participant(10, "TestUser")
        self.assertIs(result, mock_p)
        self.participants.create.assert_called_once_with(10, "TestUser")

    # ── Group ──────────────────────────────────────────────────────────

    def test_find_or_create_group_exists(self):
        mock_g = MagicMock()
        self.groups.get_by_telegram_id.return_value = mock_g
        result = self.service.find_or_create_group(1)
        self.assertIs(result, mock_g)
        self.groups.create.assert_not_called()

    def test_find_or_create_group_new(self):
        self.groups.get_by_telegram_id.return_value = None
        mock_g = MagicMock()
        self.groups.create.return_value = mock_g
        result = self.service.find_or_create_group(1)
        self.assertIs(result, mock_g)
        self.groups.create.assert_called_once_with(1)

    # ── Join / Leave ───────────────────────────────────────────────────

    def test_join_group_resolves_pending_block(self):
        self.links.get_by_santa_and_group.return_value = None
        self.groups.get_by_telegram_id.return_value = MagicMock(id=5)
        result = self.service.join_group(1, 1, "TestUser")
        self.assertEqual(result, "joined")
        self.blocked_links.resolve_pending_block.assert_called_once_with("TestUser", 1)

    def test_join_group_already_joined(self):
        self.links.get_by_santa_and_group.return_value = MagicMock()
        result = self.service.join_group(1, 1, "TestUser")
        self.assertEqual(result, "already_joined")

    def test_join_group_no_group(self):
        self.links.get_by_santa_and_group.return_value = None
        self.groups.get_by_telegram_id.return_value = None
        result = self.service.join_group(1, 1, "TestUser")
        self.assertEqual(result, "no_group")

    def test_leave_group_not_joined(self):
        self.links.get_by_santa_and_group.return_value = None
        result = self.service.leave_group(1, 1)
        self.assertEqual(result, "not_joined")

    def test_leave_group_success(self):
        mock_link = MagicMock()
        self.links.get_by_santa_and_group.return_value = mock_link
        result = self.service.leave_group(1, 1)
        self.assertEqual(result, "left")
        self.links.delete.assert_called_once_with(mock_link)

    # ── Blocking ───────────────────────────────────────────────────────

    def test_block_by_username_unknown(self):
        self.participants.get_by_username.return_value = None
        self.blocked_links.find_by_blocker_and_username.return_value = None
        result = self.service.block_by_username(1, "BlockedUser")
        self.assertEqual(result, "blocked")
        self.blocked_links.create_by_username.assert_called_once_with(1, "BlockedUser")

    def test_block_by_username_already_blocked(self):
        self.participants.get_by_username.return_value = None
        self.blocked_links.find_by_blocker_and_username.return_value = MagicMock()
        result = self.service.block_by_username(1, "BlockedUser")
        self.assertEqual(result, "already_blocked")

    def test_block_self(self):
        mock_target = MagicMock(id=1)
        self.participants.get_by_username.return_value = mock_target
        result = self.service.block_by_username(1, "Self")
        self.assertEqual(result, "self_block")

    def test_block_by_user_id_success(self):
        mock_target = MagicMock(id=5)
        self.participants.get_by_telegram_id.return_value = mock_target
        self.blocked_links.find_by_ids.return_value = None
        result = self.service.block_by_user_id(1, 20)
        self.assertEqual(result, "blocked")
        self.blocked_links.create_by_id.assert_called_once_with(1, 5)

    def test_block_by_user_id_needs_join(self):
        self.participants.get_by_telegram_id.return_value = None
        result = self.service.block_by_user_id(1, 20)
        self.assertEqual(result, "needs_join_first")

    def test_unblock_success(self):
        mock_bl = MagicMock()
        self.blocked_links.find_for_allow.return_value = mock_bl
        result = self.service.unblock(1, "BlockedUser", 0)
        self.assertTrue(result)
        self.blocked_links.delete.assert_called_once_with(mock_bl)

    def test_unblock_not_found(self):
        self.blocked_links.find_for_allow.return_value = None
        result = self.service.unblock(1, "BlockedUser", 0)
        self.assertFalse(result)

    # ── Exchange status ────────────────────────────────────────────────

    def test_get_exchange_status_no_group(self):
        self.groups.get_by_telegram_id.return_value = None
        status, links = self.service.get_exchange_status(1)
        self.assertEqual(status, "no_group")
        self.assertEqual(links, [])

    def test_get_exchange_status_not_begun(self):
        mock_group = MagicMock()
        mock_group.links = ["l1", "l2"]
        self.groups.get_by_telegram_id.return_value = mock_group
        self.links.get_first_in_group.return_value = None
        status, links = self.service.get_exchange_status(1)
        self.assertEqual(status, "not_begun")
        self.assertEqual(links, ["l1", "l2"])

    def test_get_exchange_status_finished(self):
        mock_group = MagicMock()
        mock_group.links = []
        self.groups.get_by_telegram_id.return_value = mock_group
        self.links.get_first_in_group.return_value = MagicMock(receiver_id=5)
        self.links.get_pending_notifications.return_value = []
        status, links = self.service.get_exchange_status(1)
        self.assertEqual(status, "finished")

    def test_get_exchange_status_delivery_pending(self):
        mock_group = MagicMock()
        mock_group.links = []
        self.groups.get_by_telegram_id.return_value = mock_group
        self.links.get_first_in_group.return_value = MagicMock(receiver_id=5)
        self.links.get_pending_notifications.return_value = [MagicMock()]
        status, links = self.service.get_exchange_status(1)
        self.assertEqual(status, "delivery_pending")

    def test_is_exchange_setup_no_joins(self):
        self.links.get_first_in_group.return_value = None
        result = self.service.is_exchange_setup(1)
        self.assertEqual(result, "no_joins")

    def test_is_exchange_setup_already_setup(self):
        self.links.get_first_in_group.return_value = MagicMock(receiver_id=5)
        result = self.service.is_exchange_setup(1)
        self.assertEqual(result, "already_setup")

    def test_is_exchange_setup_ready(self):
        self.links.get_first_in_group.return_value = MagicMock(receiver_id=None)
        result = self.service.is_exchange_setup(1)
        self.assertIsNone(result)

    # ── Run exchange ───────────────────────────────────────────────────

    def test_run_exchange_not_enough(self):
        self.links.get_links_in_group.return_value = [MagicMock(santa_id=1)]
        success, result = self.service.run_exchange(1)
        self.assertFalse(success)
        self.assertEqual(result, {})

    def test_run_exchange_success(self):
        self.links.get_links_in_group.return_value = [
            MagicMock(santa_id=1),
            MagicMock(santa_id=2),
        ]
        self.blocked_links.get_by_participant_ids.return_value = []
        success, result = self.service.run_exchange(1)
        self.assertTrue(success)
        self.assertEqual(len(result), 2)

    def test_reset_exchange(self):
        self.service.reset_exchange(1)
        self.links.clear_receivers_in_group.assert_called_once_with(1)

    def test_format_exception_id(self):
        eid = ExchangeService.format_exception_id()
        self.assertIsInstance(eid, str)
        self.assertEqual(len(eid.split("-")), 5)

    # ── Group options ──────────────────────────────────────────────────

    def test_group_options_defaults_when_group_missing(self):
        self.groups.get_by_telegram_id.return_value = None
        self.assertEqual(
            self.service.group_options(1),
            {"requires_address": False, "wishlist_enabled": False},
        )

    def test_group_options_reads_flags(self):
        self.groups.get_by_telegram_id.return_value = MagicMock(requires_address=True, wishlist_enabled=False)
        self.assertEqual(
            self.service.group_options(1),
            {"requires_address": True, "wishlist_enabled": False},
        )

    def test_set_group_option_updates_only_the_given_flag(self):
        self.service.set_group_option(1, requires_address=True)
        self.groups.set_requires_address.assert_called_once_with(1, True)
        self.groups.set_wishlist_enabled.assert_not_called()

    def test_set_group_option_updates_wishlist(self):
        self.service.set_group_option(1, wishlist_enabled=False)
        self.groups.set_wishlist_enabled.assert_called_once_with(1, False)
        self.groups.set_requires_address.assert_not_called()

    def test_set_group_title_delegates(self):
        self.service.set_group_title(1, "Office Exchange")
        self.groups.set_title.assert_called_once_with(1, "Office Exchange")

    # ── Wishlist ───────────────────────────────────────────────────────

    def _joined(self):
        self.groups.get_by_telegram_id.return_value = MagicMock(id=5)
        self.links.get_by_santa_and_group.return_value = MagicMock()
        self.wishlists.count_for.return_value = 0
        self.wishlists.list_for.return_value = []

    def test_add_wishlist_item_rejects_blank(self):
        self._joined()
        self.assertEqual(self.service.add_wishlist_item(1, 1, "   "), "empty")
        self.wishlists.add.assert_not_called()

    def test_add_wishlist_item_rejects_too_long(self):
        self._joined()
        self.assertEqual(self.service.add_wishlist_item(1, 1, "x" * 1025), "too_long")
        self.wishlists.add.assert_not_called()

    def test_add_wishlist_item_accepts_long_url(self):
        self._joined()
        url = "https://example.com/" + "a" * 900
        self.assertEqual(self.service.add_wishlist_item(1, 1, url), "added")
        self.wishlists.add.assert_called_once_with(5, 1, url)

    def test_add_wishlist_item_strips_whitespace(self):
        self._joined()
        self.service.add_wishlist_item(1, 1, "  a book  ")
        self.wishlists.add.assert_called_once_with(5, 1, "a book")

    def test_add_wishlist_item_requires_group(self):
        self.groups.get_by_telegram_id.return_value = None
        self.assertEqual(self.service.add_wishlist_item(1, 1, "a"), "no_group")

    def test_add_wishlist_item_requires_join(self):
        self.groups.get_by_telegram_id.return_value = MagicMock(id=5)
        self.links.get_by_santa_and_group.return_value = None
        self.assertEqual(self.service.add_wishlist_item(1, 1, "a"), "not_joined")

    def test_add_wishlist_item_rejects_when_full(self):
        self._joined()
        self.wishlists.count_for.return_value = 20
        self.assertEqual(self.service.add_wishlist_item(1, 1, "a"), "full")
        self.wishlists.add.assert_not_called()

    def test_add_wishlist_item_rejects_when_total_would_overflow(self):
        self._joined()
        self.wishlists.count_for.return_value = 3
        self.wishlists.list_for.return_value = [MagicMock(details="y" * 1024)] * 3
        self.assertEqual(self.service.add_wishlist_item(1, 1, "z" * 1024), "total_too_long")
        self.wishlists.add.assert_not_called()

    def test_list_wishlist_items_resolves_group(self):
        self._joined()
        self.service.list_wishlist_items(1, 1)
        self.wishlists.list_for.assert_called_once_with(5, 1)

    def test_list_wishlist_items_without_group_returns_empty(self):
        self.groups.get_by_telegram_id.return_value = None
        self.assertEqual(self.service.list_wishlist_items(1, 1), [])

    def test_remove_wishlist_item_by_position(self):
        self._joined()
        items = [MagicMock(id=7), MagicMock(id=9)]
        self.wishlists.list_for.return_value = items
        self.assertTrue(self.service.remove_wishlist_item(1, 1, 2))
        self.wishlists.delete.assert_called_once_with(items[1])

    def test_remove_wishlist_item_out_of_range(self):
        self._joined()
        self.assertFalse(self.service.remove_wishlist_item(1, 1, 1))
        self.wishlists.delete.assert_not_called()

    def test_clear_wishlist_delegates(self):
        self._joined()
        self.service.clear_wishlist(1, 1)
        self.wishlists.clear.assert_called_once_with(5, 1)

    def test_render_wishlist_numbers_items(self):
        items = [MagicMock(details="a"), MagicMock(details="b")]
        self.assertEqual(ExchangeService.render_wishlist("Title", items), "Title\n1. a\n2. b")

    def test_render_wishlist_without_items_is_just_the_title(self):
        self.assertEqual(ExchangeService.render_wishlist("Title", []), "Title")
