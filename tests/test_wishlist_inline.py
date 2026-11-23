import unittest
from unittest.mock import AsyncMock, Mock

from bot._migrate import run_migrations
from bot.DBConnection import DBConnection
from bot.models.Group import Group
from bot.models.Link import Link
from bot.models.Participant import Participant
from bot.SantaBot import SantaBot


class TestInlineWishlists(unittest.IsolatedAsyncioTestCase):
    """Inline mode returns one result per exchange the requester belongs to."""

    def setUp(self) -> None:
        self.db = DBConnection("sqlite://")
        with self.db.engine.connect() as connection:
            run_migrations("sqlite://", connection=connection)
        self.bot = SantaBot(self.db)
        self.session = self.bot.session

    def tearDown(self) -> None:
        self.session.close()
        self.db.engine.dispose()

    def _participant(self, user_id: int = 10) -> Participant:
        participant = Participant(telegram_id=user_id, telegram_username="TestUser")
        self.session.add(participant)
        self.session.commit()
        return participant

    def _exchange(self, chat_id: int, title: str) -> Group:
        group = Group(telegram_id=chat_id, title=title)
        self.session.add(group)
        self.session.commit()
        return group

    def _join_and_add(self, participant: Participant, group: Group, items: list[str]) -> None:
        self.session.add(Link(santa_id=participant.id, group_id=group.id))
        self.session.commit()
        for item in items:
            self.assertEqual(self.bot.exchange.add_wishlist_item(participant.id, group.telegram_id, item), "added")

    def _update(self, user_id: int = 10, query: str = "") -> Mock:
        update = Mock()
        update.effective_user.id = user_id
        update.inline_query = AsyncMock()
        update.inline_query.from_user.id = user_id
        update.inline_query.from_user.language_code = "en"
        update.inline_query.query = query
        return update

    async def _answer(self, user_id: int = 10, query: str = ""):
        update = self._update(user_id, query)
        await self.bot.inline_wishlists(update, Mock())
        update.inline_query.answer.assert_awaited_once()
        return update.inline_query.answer

    async def test_unknown_user_gets_no_results(self) -> None:
        answer = await self._answer(user_id=999)
        self.assertEqual(answer.await_args.args[0], [])

    async def test_one_result_per_exchange(self) -> None:
        participant = self._participant()
        office = self._exchange(1, "Office")
        family = self._exchange(2, "Family")
        self._join_and_add(participant, office, ["a mug"])
        self._join_and_add(participant, family, ["a scarf"])

        answer = await self._answer()
        results = answer.await_args.args[0]
        self.assertEqual([result.title for result in results], ["Office", "Family"])

    async def test_exchange_without_items_is_skipped(self) -> None:
        participant = self._participant()
        office = self._exchange(1, "Office")
        family = self._exchange(2, "Family")
        self._join_and_add(participant, office, ["a mug"])
        self._join_and_add(participant, family, [])

        answer = await self._answer()
        results = answer.await_args.args[0]
        self.assertEqual([result.title for result in results], ["Office"])

    async def test_shared_message_contains_the_items(self) -> None:
        participant = self._participant()
        office = self._exchange(1, "Office")
        self._join_and_add(participant, office, ["a mug", "https://example.com/gift"])

        answer = await self._answer()
        result = answer.await_args.args[0][0]
        text = result.input_message_content.message_text
        self.assertIn("Office", text)
        self.assertIn("- a mug", text)
        self.assertIn("https://example.com/gift", text)
        self.assertTrue(result.input_message_content.link_preview_options.is_disabled)

    async def test_filter_by_chat_id_narrows_results(self) -> None:
        participant = self._participant()
        office = self._exchange(1, "Office")
        family = self._exchange(2, "Family")
        self._join_and_add(participant, office, ["a mug"])
        self._join_and_add(participant, family, ["a scarf"])

        answer = await self._answer(query="2")
        results = answer.await_args.args[0]
        self.assertEqual([result.title for result in results], ["Family"])

    async def test_results_are_personal_and_uncached(self) -> None:
        participant = self._participant()
        self._join_and_add(participant, self._exchange(1, "Office"), ["a mug"])

        answer = await self._answer()
        self.assertEqual(answer.await_args.kwargs["cache_time"], 0)
        self.assertTrue(answer.await_args.kwargs["is_personal"])
