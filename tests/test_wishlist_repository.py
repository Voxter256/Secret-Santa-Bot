import unittest

from bot._migrate import run_migrations
from bot.DBConnection import DBConnection
from bot.models.Group import Group
from bot.models.Participant import Participant
from bot.repositories.sqlalchemy_repos import SqlWishlistRepository


class TestWishlistRepository(unittest.TestCase):
    """Wishlist rows are scoped to a (group, participant) pair."""

    def setUp(self) -> None:
        self.db = DBConnection("sqlite://")
        with self.db.engine.connect() as connection:
            run_migrations("sqlite://", connection=connection)
        self.session = self.db.session
        self.repo = SqlWishlistRepository(self.session)
        self.group = Group(telegram_id=1)
        self.other_group = Group(telegram_id=2)
        self.me = Participant(telegram_id=10)
        self.other = Participant(telegram_id=20)
        self.session.add_all([self.group, self.other_group, self.me, self.other])
        self.session.commit()

    def tearDown(self) -> None:
        self.session.close()
        self.db.engine.dispose()

    def test_add_and_list_in_insertion_order(self) -> None:
        self.repo.add(self.group.id, self.me.id, "something")
        self.repo.add(self.group.id, self.me.id, "https://example.com/x")
        details = [item.details for item in self.repo.list_for(self.group.id, self.me.id)]
        self.assertEqual(details, ["something", "https://example.com/x"])

    def test_list_is_scoped_to_group_and_participant(self) -> None:
        self.repo.add(self.group.id, self.me.id, "mine")
        self.repo.add(self.other_group.id, self.me.id, "elsewhere")
        self.repo.add(self.group.id, self.other.id, "someone else")
        details = [item.details for item in self.repo.list_for(self.group.id, self.me.id)]
        self.assertEqual(details, ["mine"])

    def test_count_for(self) -> None:
        self.repo.add(self.group.id, self.me.id, "a")
        self.repo.add(self.group.id, self.me.id, "b")
        self.assertEqual(self.repo.count_for(self.group.id, self.me.id), 2)
        self.assertEqual(self.repo.count_for(self.other_group.id, self.me.id), 0)

    def test_delete_removes_only_that_item(self) -> None:
        first = self.repo.add(self.group.id, self.me.id, "a")
        self.repo.add(self.group.id, self.me.id, "b")
        self.repo.delete(first)
        details = [item.details for item in self.repo.list_for(self.group.id, self.me.id)]
        self.assertEqual(details, ["b"])

    def test_clear_removes_only_that_group(self) -> None:
        self.repo.add(self.group.id, self.me.id, "a")
        self.repo.add(self.other_group.id, self.me.id, "b")
        self.repo.clear(self.group.id, self.me.id)
        self.assertEqual(self.repo.list_for(self.group.id, self.me.id), [])
        self.assertEqual(len(self.repo.list_for(self.other_group.id, self.me.id)), 1)

    def test_groups_with_items_is_distinct(self) -> None:
        self.repo.add(self.group.id, self.me.id, "a")
        self.repo.add(self.group.id, self.me.id, "b")
        self.repo.add(self.other_group.id, self.me.id, "c")
        self.repo.add(self.group.id, self.other.id, "d")
        self.assertEqual(
            sorted(self.repo.groups_with_items(self.me.id)),
            sorted([self.group.id, self.other_group.id]),
        )

    def test_get_returns_none_for_missing(self) -> None:
        self.assertIsNone(self.repo.get(999))
