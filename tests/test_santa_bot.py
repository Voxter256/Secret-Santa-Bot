import datetime
import logging
import os
import unittest
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import func, inspect, select, text
from telegram import ForceReply
from telegram.error import BadRequest, Forbidden

from bot._migrate import run_migrations
from bot.DBConnection import DBConnection
from bot.log_context import CorrelationFilter
from bot.models.BlockedLink import BlockedLink
from bot.models.Feedback import Feedback
from bot.models.Group import Group
from bot.models.Link import Link
from bot.models.Participant import Participant
from bot.SantaBot import SantaBot


class MigratedDatabaseTestCase(unittest.IsolatedAsyncioTestCase):
    """Per-test in-memory SQLite database whose schema is built by the real migrations."""

    dbConnection: DBConnection
    bot: SantaBot

    def setUp(self) -> None:
        self.db_url = "sqlite://"
        self.dbConnection = DBConnection(self.db_url)
        with self.dbConnection.engine.connect() as connection:
            run_migrations(self.db_url, connection=connection)
        self.bot = SantaBot(self.dbConnection)

    def tearDown(self) -> None:
        self.bot.session.close()
        self.dbConnection.engine.dispose()

    def _make_update_mock(
        self, chat_id=1, user_id=10, username="TestUser", chat_type="group", language_code="en", message_date=None
    ):
        import datetime

        update = MagicMock()
        update.effective_chat.id = chat_id
        update.effective_chat.type = chat_type
        update.effective_chat.title = "Test Group"
        update.effective_user.id = user_id
        update.effective_user.username = username
        update.effective_user.name = username
        update.effective_user.language_code = language_code
        update.effective_message.text = ""
        if message_date is None:
            message_date = datetime.datetime.now(datetime.UTC)
        update.effective_message.date = message_date
        update.effective_message.reply_to_message = None
        return update


class TestSchemaFromMigrations(MigratedDatabaseTestCase):
    """The test schema must be produced by Alembic, not Base.metadata."""

    def test_migrations_create_expected_tables(self) -> None:
        tables = set(inspect(self.dbConnection.engine).get_table_names())
        self.assertEqual(
            tables,
            {
                "alembic_version",
                "blocked_links",
                "exchange_events",
                "feedback",
                "groups",
                "links",
                "participants",
                "wishlist_items",
            },
        )

    def test_database_reports_head_revision(self) -> None:
        head = ScriptDirectory.from_config(Config("alembic.ini")).get_current_head()
        with self.dbConnection.engine.connect() as connection:
            revision = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
        self.assertEqual(revision, head)

    def test_wishlist_items_are_group_scoped(self) -> None:
        inspector = inspect(self.dbConnection.engine)
        columns = {c["name"]: c for c in inspector.get_columns("wishlist_items")}
        self.assertFalse(columns["group_id"]["nullable"])
        self.assertFalse(columns["participant_id"]["nullable"])
        self.assertFalse(columns["details"]["nullable"])

        indexes = {i["name"]: i["column_names"] for i in inspector.get_indexes("wishlist_items")}
        self.assertEqual(
            indexes.get("ix_wishlist_items_group_participant"),
            ["group_id", "participant_id"],
        )

        foreign_keys = inspector.get_foreign_keys("wishlist_items")
        self.assertEqual(
            {fk["referred_table"] for fk in foreign_keys},
            {"groups", "participants"},
        )

    def test_groups_track_when_the_bot_lost_access(self) -> None:
        columns = {c["name"]: c for c in inspect(self.dbConnection.engine).get_columns("groups")}
        self.assertIn("left_at", columns)
        self.assertTrue(columns["left_at"]["nullable"])

    def test_new_groups_opt_out_by_default(self) -> None:
        group = Group(telegram_id=123)
        self.bot.session.add(group)
        self.bot.session.commit()
        self.assertFalse(group.requires_address)
        self.assertFalse(group.wishlist_enabled)


class TestGroupOptionsMigration(unittest.TestCase):
    """The backfill keeps existing groups delivering addresses; new groups opt in."""

    def setUp(self) -> None:
        self.db = DBConnection("sqlite://")

    def tearDown(self) -> None:
        self.db.session.close()
        self.db.engine.dispose()

    @staticmethod
    def _upgrade(connection, revision: str = "head") -> None:
        run_migrations("sqlite://", connection=connection, revision=revision)

    @staticmethod
    def _insert_group(connection, telegram_id: int) -> None:
        connection.execute(text(f"INSERT INTO groups (telegram_id) VALUES ({telegram_id})"))  # noqa: S608

    @staticmethod
    def _value(connection, column: str, telegram_id: int):
        return connection.execute(
            text(f"SELECT {column} FROM groups WHERE telegram_id = {telegram_id}")  # noqa: S608
        ).scalar_one()

    def test_existing_group_is_backfilled_to_require_address(self) -> None:
        with self.db.engine.connect() as connection:
            self._upgrade(connection, "60e6fe52a838")
            self._insert_group(connection, 1)
            self._upgrade(connection)
            self.assertEqual(self._value(connection, "requires_address", 1), 1)

    def test_group_created_after_migration_opts_out(self) -> None:
        with self.db.engine.connect() as connection:
            self._upgrade(connection)
            self._insert_group(connection, 2)
            self.assertEqual(self._value(connection, "requires_address", 2), 0)

    def test_wishlist_stays_off_for_existing_groups(self) -> None:
        with self.db.engine.connect() as connection:
            self._upgrade(connection, "60e6fe52a838")
            self._insert_group(connection, 3)
            self._upgrade(connection)
            self.assertEqual(self._value(connection, "wishlist_enabled", 3), 0)


class TestSantaBot(MigratedDatabaseTestCase):
    @patch.object(SantaBot, "reply_message")
    @patch.object(SantaBot, "send_message")
    @patch.object(SantaBot, "is_update_expired")
    async def test_start(self, mock_expired: MagicMock, mock_send: MagicMock, mock_reply: MagicMock):
        await self.private_chat_required(mock_expired, mock_reply)

    @patch.object(SantaBot, "reply_message")
    @patch.object(SantaBot, "send_message")
    @patch.object(SantaBot, "is_update_expired")
    async def test_start_exchange_no_group_links(
        self, mock_expired: MagicMock, mock_send: MagicMock, mock_reply: MagicMock
    ):
        mock_expired.return_value = False
        context = Mock()
        update = MagicMock()
        update.effective_chat.id = 1
        await self.bot.start_exchange(update, context)
        mock_reply.assert_called_with(update=update, text="No one has Joined!")

    async def private_chat_required(self, mock_expired, mock_reply):
        with self.subTest(private_chat_required=True):
            mock_expired.return_value = False
            context = Mock()
            update = MagicMock()
            update.effective_user.id = 1
            update.effective_user.username = "Test"
            update.effective_chat.type = "NotPrivate"
            await self.bot.start(update, context)
            mock_reply.assert_called_with(update=update, text="You must send me this in a private chat")


class TestPairingLogic(unittest.TestCase):
    """Pure unit tests for SantaBot.find_combination and get_random_pairing — no DB needed."""

    def test_find_combination_simple_pairing(self):
        participants = [1, 2]
        success, result = SantaBot.find_combination(participants, [])
        self.assertTrue(success)
        self.assertEqual(len(result), 2)
        self.assertIn(1, result)
        self.assertIn(2, result)
        self.assertNotEqual(result[1], 1)
        self.assertNotEqual(result[2], 2)

    def test_find_combination_three_participants(self):
        participants = [1, 2, 3]
        success, result = SantaBot.find_combination(participants, [])
        self.assertTrue(success)
        self.assertEqual(len(result), 3)
        for santa, receiver in result.items():
            self.assertNotEqual(santa, receiver)
        self.assertEqual(set(result.keys()), {1, 2, 3})
        self.assertEqual(set(result.values()), {1, 2, 3})

    def test_find_combination_with_blocked_pairings(self):
        participants = [1, 2, 3]
        blocked = [[1, 2]]
        success, result = SantaBot.find_combination(participants, blocked)
        if success:
            self.assertEqual(len(result), 3)
            self.assertNotEqual(result.get(1), 2)
            self.assertNotEqual(result.get(2), 1)

    def test_find_combination_impossible_all_blocked(self):
        participants = [1, 2]
        blocked = [[1, 2]]
        success, result = SantaBot.find_combination(participants, blocked)
        self.assertFalse(success)
        self.assertEqual(result, {})

    def test_find_combination_large_group(self):
        participants = list(range(1, 11))
        success, result = SantaBot.find_combination(participants, [])
        self.assertTrue(success)
        self.assertEqual(len(result), 10)
        santas = set(result.keys())
        receivers = set(result.values())
        self.assertEqual(santas, set(participants))
        self.assertEqual(receivers, set(participants))
        for santa, receiver in result.items():
            self.assertNotEqual(santa, receiver)

    def test_find_combination_single_participant(self):
        participants = [1]
        success, result = SantaBot.find_combination(participants, [])
        self.assertFalse(success)
        self.assertEqual(result, {})

    def test_find_combination_self_block_ignored(self):
        participants = [1, 2]
        blocked = [[1, 1]]
        success, result = SantaBot.find_combination(participants, blocked)
        self.assertTrue(success)
        self.assertEqual(len(result), 2)

    def test_find_combination_multi_blocked_preserves_valid_pairing(self):
        participants = [1, 2, 3]
        blocked = [[1, 2], [2, 1]]
        success, result = SantaBot.find_combination(participants, blocked)
        if success:
            self.assertNotEqual(result.get(1), 2)
            self.assertNotEqual(result.get(2), 1)

    def test_get_random_pairing_direct(self):
        sorted_permutations = [(1, {2}), (2, {1})]
        success, result = SantaBot.get_random_pairing(sorted_permutations)
        self.assertTrue(success)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[1], 2)
        self.assertEqual(result[2], 1)

    def test_get_random_pairing_with_gifting_list(self):
        sorted_permutations = [(2, {3}), (3, {2})]
        success, result = SantaBot.get_random_pairing(sorted_permutations, gifting=[1])
        self.assertTrue(success)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[2], 3)
        self.assertEqual(result[3], 2)


class TestSantaBotHandlers(MigratedDatabaseTestCase):
    """Tests for message handler flows and set_and_send_individual_result."""

    # -- helpers --

    async def _setup_participant(self, user_id=10, username="TestUser", address="123 Main St"):
        p = Participant(telegram_id=user_id, telegram_username=username, address=address)
        self.bot.session.add(p)
        self.bot.session.commit()
        return p

    async def _setup_group(self, chat_id=1):
        g = Group(telegram_id=chat_id)
        self.bot.session.add(g)
        self.bot.session.commit()
        return g

    async def _setup_link(self, santa_id, group_id):
        link = Link(santa_id=santa_id, group_id=group_id)
        self.bot.session.add(link)
        self.bot.session.commit()
        return link

    # -- join handler tests --

    @patch.object(SantaBot, "reply_message")
    @patch.object(SantaBot, "send_message")
    @patch.object(SantaBot, "is_update_expired")
    async def test_join_private_chat_rejected(self, mock_expired, mock_send, mock_reply):
        mock_expired.return_value = False
        update = self._make_update_mock(chat_type="private")
        context = Mock()
        await self.bot.join(update, context)
        mock_reply.assert_called_with(update=update, text="You must begin from a group chat")

    @patch.object(SantaBot, "reply_message")
    @patch.object(SantaBot, "send_message")
    @patch.object(SantaBot, "is_update_expired")
    async def test_join_no_start(self, mock_expired, mock_send, mock_reply):
        mock_expired.return_value = False
        update = self._make_update_mock()
        context = Mock()
        await self.bot.join(update, context)
        mock_reply.assert_called_once()
        args, kwargs = mock_reply.call_args
        text = kwargs.get("text", args[0] if args else "")
        self.assertIn("start", text)

    @patch.object(SantaBot, "reply_message")
    @patch.object(SantaBot, "send_message")
    @patch.object(SantaBot, "is_update_expired")
    async def test_join_without_address(self, mock_expired, mock_send, mock_reply):
        mock_expired.return_value = False
        p = Participant(telegram_id=10, telegram_username="TestUser", address=None)
        self.bot.session.add(p)
        self.bot.session.commit()
        self.bot.exchange.find_or_create_group(1)
        update = self._make_update_mock()
        await self.bot.join(update, Mock())
        mock_reply.assert_called_with(update=update, text="OK, you're in!")
        mock_send.assert_not_called()
        self.assertEqual(self.bot.session.scalar(select(func.count()).select_from(Link)), 1)

    @patch.object(SantaBot, "reply_message")
    @patch.object(SantaBot, "send_message")
    @patch.object(SantaBot, "is_update_expired")
    async def test_start_new_participant_does_not_prompt_for_address(self, mock_expired, mock_send, mock_reply):
        mock_expired.return_value = False
        update = self._make_update_mock(chat_type="private")
        await self.bot.start(update, Mock())
        texts = [call.kwargs["text"] for call in mock_send.call_args_list]
        self.assertEqual(texts[0], "Hello! Lets get you setup!")
        self.assertIn("/address", texts[1])
        self.assertNotIn("What is your address", texts[1])
        for call in mock_send.call_args_list:
            self.assertNotIn("reply_markup", call.kwargs)

    @patch.object(SantaBot, "reply_message")
    @patch.object(SantaBot, "send_message")
    @patch.object(SantaBot, "is_update_expired")
    async def test_start_without_address_sends_hint_only(self, mock_expired, mock_send, mock_reply):
        mock_expired.return_value = False
        p = Participant(telegram_id=10, telegram_username="TestUser", address=None)
        self.bot.session.add(p)
        self.bot.session.commit()
        update = self._make_update_mock(chat_type="private")
        await self.bot.start(update, Mock())
        texts = [call.kwargs["text"] for call in mock_send.call_args_list]
        self.assertEqual(texts, ["Use /address to share a mailing address, or /wish for wishlists."])

    @patch.object(SantaBot, "reply_message")
    @patch.object(SantaBot, "send_message")
    @patch.object(SantaBot, "is_update_expired")
    async def test_start_with_address_echoes_it(self, mock_expired, mock_send, mock_reply):
        mock_expired.return_value = False
        p = Participant(telegram_id=10, telegram_username="TestUser", address="123 Main St")
        self.bot.session.add(p)
        self.bot.session.commit()
        update = self._make_update_mock(chat_type="private")
        await self.bot.start(update, Mock())
        texts = [call.kwargs["text"] for call in mock_send.call_args_list]
        self.assertEqual(len(texts), 1)
        self.assertIn("123 Main St", texts[0])
        self.assertIn("/address", texts[0])

    @patch.object(SantaBot, "reply_message")
    @patch.object(SantaBot, "is_update_expired")
    async def test_address_reply_saves_when_awaiting(self, mock_expired, mock_reply):
        mock_expired.return_value = False
        p = Participant(telegram_id=10, telegram_username="TestUser")
        self.bot.session.add(p)
        self.bot.session.commit()
        self.bot.bot_id = 999
        update = self._make_update_mock(chat_type="private")
        update.effective_message.text = "42 Galaxy Way"
        update.effective_message.reply_to_message = MagicMock()
        update.effective_message.reply_to_message.from_user.id = 999
        context = Mock()
        context.user_data = {"awaiting_address": True}
        await self.bot.address(update, context)
        self.bot.session.refresh(p)
        self.assertEqual(p.address, "42 Galaxy Way")
        self.assertNotIn("awaiting_address", context.user_data)

    @patch.object(SantaBot, "reply_message")
    @patch.object(SantaBot, "is_update_expired")
    async def test_address_reply_ignored_without_pending_prompt(self, mock_expired, mock_reply):
        mock_expired.return_value = False
        p = Participant(telegram_id=10, telegram_username="TestUser")
        self.bot.session.add(p)
        self.bot.session.commit()
        self.bot.bot_id = 999
        update = self._make_update_mock(chat_type="private")
        update.effective_message.text = "42 Galaxy Way"
        update.effective_message.reply_to_message = MagicMock()
        update.effective_message.reply_to_message.from_user.id = 999
        context = Mock()
        context.user_data = {}
        await self.bot.address(update, context)
        self.bot.session.refresh(p)
        self.assertIsNone(p.address)

    @patch.object(SantaBot, "reply_message")
    @patch.object(SantaBot, "send_message")
    @patch.object(SantaBot, "is_update_expired")
    async def test_join_no_group_hello(self, mock_expired, mock_send, mock_reply):
        mock_expired.return_value = False
        await self._setup_participant()
        update = self._make_update_mock()
        context = Mock()
        await self.bot.join(update, context)
        mock_reply.assert_called_with(update=update, text="Someone must say /hello first!")

    @patch.object(SantaBot, "reply_message")
    @patch.object(SantaBot, "send_message")
    @patch.object(SantaBot, "is_update_expired")
    async def test_join_success(self, mock_expired, mock_send, mock_reply):
        mock_expired.return_value = False
        await self._setup_participant()
        await self._setup_group()
        update = self._make_update_mock()
        context = Mock()
        await self.bot.join(update, context)
        mock_reply.assert_called_with(update=update, text="OK, you're in!")
        participant = self.bot.session.scalars(select(Participant).where(Participant.telegram_id == 10)).first()
        group = self.bot.session.scalars(select(Group).where(Group.telegram_id == 1)).first()
        link = self.bot.session.scalars(
            select(Link).where(Link.santa_id == participant.id, Link.group_id == group.id)
        ).first()
        self.assertIsNotNone(link)

    @patch.object(SantaBot, "reply_message")
    @patch.object(SantaBot, "send_message")
    @patch.object(SantaBot, "is_update_expired")
    async def test_join_already_joined(self, mock_expired, mock_send, mock_reply):
        mock_expired.return_value = False
        p = await self._setup_participant()
        g = await self._setup_group()
        await self._setup_link(p.id, g.id)
        update = self._make_update_mock()
        context = Mock()
        await self.bot.join(update, context)
        mock_reply.assert_called_with(update=update, text="You have already joined!")

    # -- leave handler tests --

    @patch.object(SantaBot, "reply_message")
    @patch.object(SantaBot, "send_message")
    @patch.object(SantaBot, "is_update_expired")
    async def test_leave_not_joined(self, mock_expired, mock_send, mock_reply):
        mock_expired.return_value = False
        await self._setup_participant()
        await self._setup_group()
        update = self._make_update_mock()
        context = Mock()
        await self.bot.leave(update, context)
        mock_reply.assert_called_with(update=update, text="You never joined")

    @patch.object(SantaBot, "reply_message")
    @patch.object(SantaBot, "send_message")
    @patch.object(SantaBot, "is_update_expired")
    async def test_leave_success(self, mock_expired, mock_send, mock_reply):
        mock_expired.return_value = False
        p = await self._setup_participant()
        g = await self._setup_group()
        await self._setup_link(p.id, g.id)
        update = self._make_update_mock()
        context = Mock()
        await self.bot.leave(update, context)
        mock_reply.assert_called_with(update=update, text="Done.")
        link = self.bot.session.scalars(select(Link).where(Link.santa_id == p.id)).first()
        self.assertIsNone(link)

    # -- not_command handler tests --

    @patch.object(SantaBot, "reply_message")
    @patch.object(SantaBot, "send_message")
    @patch.object(SantaBot, "is_update_expired")
    async def test_not_command_block_by_username(self, mock_expired, mock_send, mock_reply):
        mock_expired.return_value = False
        p = await self._setup_participant()
        await self._setup_group()
        update = self._make_update_mock()
        entity_mock = MagicMock()
        entity_mock.type = "mention"
        update.effective_message.parse_entities.return_value = {entity_mock: "@BlockedUser"}
        context = Mock()
        await self.bot.not_command(update, context)
        blocked_link = self.bot.session.scalars(
            select(BlockedLink).where(BlockedLink.participant_id == p.id, BlockedLink.blocked_username == "BlockedUser")
        ).first()
        self.assertIsNotNone(blocked_link)

    @patch.object(SantaBot, "reply_message")
    @patch.object(SantaBot, "send_message")
    @patch.object(SantaBot, "is_update_expired")
    async def test_not_command_block_by_id(self, mock_expired, mock_send, mock_reply):
        mock_expired.return_value = False
        p1 = await self._setup_participant(user_id=10, username="UserA")
        p2 = await self._setup_participant(user_id=20, username="UserB")
        await self._setup_group()
        update = self._make_update_mock(user_id=10, username="UserA")
        entity_mock = MagicMock()
        entity_mock.type = "text_mention"
        entity_mock.user.id = 20
        update.effective_message.parse_entities.return_value = {entity_mock: "UserB"}
        context = Mock()
        await self.bot.not_command(update, context)
        blocked_link = self.bot.session.scalars(
            select(BlockedLink).where(BlockedLink.participant_id == p1.id, BlockedLink.blocked_id == p2.id)
        ).first()
        self.assertIsNotNone(blocked_link)
        mock_reply.assert_called_with(update=update, text="OK, you can no longer matched with that participant.")

    @patch.object(SantaBot, "reply_message")
    @patch.object(SantaBot, "send_message")
    @patch.object(SantaBot, "is_update_expired")
    async def test_not_command_self_block(self, mock_expired, mock_send, mock_reply):
        mock_expired.return_value = False
        await self._setup_participant()
        await self._setup_group()
        update = self._make_update_mock()
        entity_mock = MagicMock()
        entity_mock.type = "mention"
        update.effective_message.parse_entities.return_value = {entity_mock: "@TestUser"}
        context = Mock()
        await self.bot.not_command(update, context)
        mock_reply.assert_called_with(update=update, text="Don't worry, you won't get yourself")

    # -- allow handler tests --

    @patch.object(SantaBot, "reply_message")
    @patch.object(SantaBot, "send_message")
    @patch.object(SantaBot, "is_update_expired")
    async def test_allow_remove_block_by_username(self, mock_expired, mock_send, mock_reply):
        mock_expired.return_value = False
        p = await self._setup_participant()
        blocked_user = Participant(telegram_id=99, telegram_username="BlockedUser", address="Nowhere")
        self.bot.session.add(blocked_user)
        await self._setup_group()
        self.bot.session.add(BlockedLink(participant_id=p.id, blocked_username="BlockedUser"))
        self.bot.session.commit()
        update = self._make_update_mock()
        entity_mock = MagicMock()
        entity_mock.type = "mention"
        update.effective_message.parse_entities.return_value = {entity_mock: "@BlockedUser"}
        context = Mock()
        await self.bot.allow(update, context)
        blocked_link = self.bot.session.scalars(
            select(BlockedLink).where(BlockedLink.participant_id == p.id, BlockedLink.blocked_username == "BlockedUser")
        ).first()
        self.assertIsNone(blocked_link)
        mock_reply.assert_called_with(update=update, text="You can now be assigned to @BlockedUser")

    @patch.object(SantaBot, "reply_message")
    @patch.object(SantaBot, "send_message")
    @patch.object(SantaBot, "is_update_expired")
    async def test_allow_not_blocked(self, mock_expired, mock_send, mock_reply):
        mock_expired.return_value = False
        await self._setup_participant()
        blocked_user = Participant(telegram_id=99, telegram_username="BlockedUser", address="Nowhere")
        self.bot.session.add(blocked_user)
        self.bot.session.commit()
        await self._setup_group()
        update = self._make_update_mock()
        entity_mock = MagicMock()
        entity_mock.type = "mention"
        update.effective_message.parse_entities.return_value = {entity_mock: "@BlockedUser"}
        context = Mock()
        await self.bot.allow(update, context)
        mock_reply.assert_called_with(update=update, text="@BlockedUser was not blocked by you.")

    # -- status handler tests --

    @patch.object(SantaBot, "reply_message")
    @patch.object(SantaBot, "send_message")
    @patch.object(SantaBot, "is_update_expired")
    async def test_status_private_chat_rejected(self, mock_expired, mock_send, mock_reply):
        mock_expired.return_value = False
        update = self._make_update_mock(chat_type="private")
        context = Mock()
        await self.bot.status(update, context)
        mock_reply.assert_called_with(update=update, text="You must begin from a group chat")

    @patch.object(SantaBot, "reply_message")
    @patch.object(SantaBot, "send_message")
    @patch.object(SantaBot, "is_update_expired")
    async def test_status_no_group(self, mock_expired, mock_send, mock_reply):
        mock_expired.return_value = False
        update = self._make_update_mock()
        context = Mock()
        await self.bot.status(update, context)
        mock_reply.assert_called_with(update=update, text="Someone must say /hello first!")

    @patch.object(SantaBot, "reply_message")
    @patch.object(SantaBot, "send_message")
    @patch.object(SantaBot, "is_update_expired")
    async def test_status_exchange_not_begun(self, mock_expired, mock_send, mock_reply):
        mock_expired.return_value = False
        await self._setup_participant()
        await self._setup_group()
        update = self._make_update_mock()
        context = Mock()
        await self.bot.status(update, context)
        mock_reply.assert_called_once()
        args, kwargs = mock_reply.call_args
        text = kwargs.get("text", args[0] if args else "")
        self.assertIn("The exchange has not begun", text)

    @patch.object(SantaBot, "reply_message")
    @patch.object(SantaBot, "send_message")
    @patch.object(SantaBot, "is_update_expired")
    async def test_status_with_participants(self, mock_expired, mock_send, mock_reply):
        mock_expired.return_value = False
        p = await self._setup_participant()
        g = await self._setup_group()
        await self._setup_link(p.id, g.id)
        update = self._make_update_mock()
        member_mock = AsyncMock()
        member_mock.user.name = "TestUser"
        update.effective_chat.get_member = AsyncMock(return_value=member_mock)
        context = Mock()
        await self.bot.status(update, context)
        mock_reply.assert_called_once()
        args, kwargs = mock_reply.call_args
        text = kwargs.get("text", args[0] if args else "")
        self.assertIn("TestUser", text)

    @patch.object(SantaBot, "reply_message")
    @patch.object(SantaBot, "send_message")
    @patch.object(SantaBot, "is_update_expired")
    async def test_status_reports_pending_deliveries(self, mock_expired, mock_send, mock_reply):
        mock_expired.return_value = False
        await self._setup_delivery()
        update = self._make_update_mock(chat_type="group")
        update.effective_chat.get_member = AsyncMock(return_value=self._member("Receiver"))

        await self.bot.status(update, Mock())

        text = mock_reply.call_args.kwargs["text"]
        self.assertIn("were not messaged", text)
        self.assertIn("Santa", text)
        self.assertIn("/start_exchange", text)

    @patch.object(SantaBot, "reply_message")
    @patch.object(SantaBot, "send_message")
    @patch.object(SantaBot, "is_update_expired")
    async def test_status_reports_finished_after_delivery(self, mock_expired, mock_send, mock_reply):
        mock_expired.return_value = False
        _santa, _receiver, _group, link = await self._setup_delivery()
        self.bot.exchange.mark_delivered(link)
        update = self._make_update_mock(chat_type="group")
        update.effective_chat.get_member = AsyncMock(return_value=self._member("Receiver"))

        await self.bot.status(update, Mock())

        text = mock_reply.call_args.kwargs["text"]
        self.assertIn("The exchange has finished", text)
        self.assertNotIn("were not messaged", text)

    # -- exchange delivery tests --

    async def _setup_delivery(self, with_receiver=True):
        santa = Participant(telegram_id=10, telegram_username="Santa", address="North Pole")
        receiver = Participant(telegram_id=20, telegram_username="Receiver", address="Somewhere")
        group = Group(telegram_id=1)
        self.bot.session.add_all([santa, receiver, group])
        self.bot.session.commit()
        link = Link(
            santa_id=santa.id,
            receiver_id=receiver.id if with_receiver else None,
            group_id=group.id,
        )
        self.bot.session.add(link)
        self.bot.session.commit()
        return santa, receiver, group, link

    def _delivery_update(self):
        update = MagicMock()
        update.effective_chat.id = 1
        update.effective_chat.title = "Test Group"
        member = AsyncMock()
        member.user.name = "Receiver"
        update.effective_chat.get_member = AsyncMock(return_value=member)
        return update

    async def test_deliver_pending_marks_notified(self):
        santa, _receiver, _group, link = await self._setup_delivery()
        update = self._delivery_update()
        gettext_mock = MagicMock(side_effect=lambda s: s)

        with patch.object(SantaBot, "send_message", new_callable=AsyncMock) as mock_send:
            with patch.object(SantaBot, "reply_message", new_callable=AsyncMock):
                await self.bot.deliver_pending(1, update, Mock(), gettext_mock)

        self.bot.session.refresh(link)
        self.assertIsNotNone(link.notified_at)
        mock_send.assert_called_once()
        _args, kwargs = mock_send.call_args
        self.assertEqual(kwargs["chat_id"], santa.telegram_id)
        self.assertIn("Receiver", kwargs["text"])

    async def test_deliver_pending_continues_after_blocked_santa(self):
        _santa, _receiver, group, link = await self._setup_delivery()
        blocked = Participant(telegram_id=30, telegram_username="Blocker", address="North Pole")
        victim = Participant(telegram_id=40, telegram_username="Victim", address="South Pole")
        self.bot.session.add_all([blocked, victim])
        self.bot.session.commit()
        blocked_link = Link(santa_id=blocked.id, receiver_id=victim.id, group_id=group.id)
        self.bot.session.add(blocked_link)
        self.bot.session.commit()

        update = self._delivery_update()
        gettext_mock = MagicMock(side_effect=lambda s: s)

        async def fake_send(context=None, chat_id=None, text=None, reply_markup=None, link_preview_options=None):
            if chat_id == 30:
                raise Forbidden("Bot was blocked by the user")
            return MagicMock()

        with patch.object(SantaBot, "send_message", new_callable=AsyncMock, side_effect=fake_send):
            with patch.object(SantaBot, "reply_message", new_callable=AsyncMock) as mock_reply:
                await self.bot.deliver_pending(1, update, Mock(), gettext_mock)

        self.bot.session.refresh(link)
        self.bot.session.refresh(blocked_link)
        self.assertIsNotNone(link.notified_at)
        self.assertIsNone(blocked_link.notified_at)
        self.assertIn("@Blocker", mock_reply.call_args.kwargs["text"])

    async def test_deliver_pending_is_idempotent(self):
        await self._setup_delivery()
        update = self._delivery_update()
        gettext_mock = MagicMock(side_effect=lambda s: s)

        with patch.object(SantaBot, "send_message", new_callable=AsyncMock) as mock_send:
            with patch.object(SantaBot, "reply_message", new_callable=AsyncMock):
                await self.bot.deliver_pending(1, update, Mock(), gettext_mock)
                await self.bot.deliver_pending(1, update, Mock(), gettext_mock)

        self.assertEqual(mock_send.call_count, 1)

    async def test_send_individual_result_requires_receiver(self):
        link = MagicMock()
        link.santa = Participant(telegram_id=10)
        link.receiver = None

        delivered, reason = await self.bot.send_individual_result(link, self._delivery_update(), Mock(), MagicMock())

        self.assertFalse(delivered)
        self.assertEqual(reason, "missing participant")

    async def test_send_individual_result_treats_bad_request_as_unreachable(self):
        _santa, _receiver, _group, link = await self._setup_delivery()

        with patch.object(
            SantaBot,
            "send_message",
            new_callable=AsyncMock,
            side_effect=BadRequest("Chat not found"),
        ):
            delivered, reason = await self.bot.send_individual_result(
                link, self._delivery_update(), Mock(), MagicMock()
            )

        self.assertFalse(delivered)
        self.assertIn("Chat not found", reason)

    def test_result_message_omits_address_when_not_required(self):
        receiver = Participant(telegram_id=20, telegram_username="Receiver", address="Somewhere")
        chat = MagicMock(title="Test Group")
        text = SantaBot.generate_result_message(chat, receiver, "Receiver", lambda s: s, requires_address=False)
        self.assertNotIn("address", text.lower())
        self.assertNotIn("Somewhere", text)

    def test_result_message_includes_address_when_required(self):
        receiver = Participant(telegram_id=20, telegram_username="Receiver", address="Somewhere")
        chat = MagicMock(title="Test Group")
        text = SantaBot.generate_result_message(chat, receiver, "Receiver", lambda s: s, requires_address=True)
        self.assertIn("Somewhere", text)

    def test_result_message_uses_placeholder_for_missing_address(self):
        receiver = Participant(telegram_id=20, telegram_username="Receiver", address=None)
        chat = MagicMock(title="Test Group")
        text = SantaBot.generate_result_message(chat, receiver, "Receiver", lambda s: s, requires_address=True)
        self.assertIn("?", text)

    def test_describe_participant_falls_back_to_telegram_id(self):
        self.assertEqual(SantaBot.describe_participant(Participant(telegram_id=42)), "42")
        self.assertEqual(
            SantaBot.describe_participant(Participant(telegram_id=42, telegram_username="someone")),
            "@someone",
        )

    async def test_pairing_persists_when_delivery_fails(self):
        santa, receiver, _group, link = await self._setup_delivery(with_receiver=False)
        update = self._make_update_mock(chat_type="group")
        gettext_mock = MagicMock(side_effect=lambda s: s)

        async def blocked_send(context=None, chat_id=None, text=None, reply_markup=None, link_preview_options=None):
            raise Forbidden("Bot was blocked by the user")

        with patch.object(SantaBot, "send_message", new_callable=AsyncMock, side_effect=blocked_send):
            with patch.object(SantaBot, "reply_message", new_callable=AsyncMock) as mock_reply:
                await self.bot.save_and_send_exchange_results({santa.id: receiver.id}, update, Mock(), gettext_mock)

        self.bot.session.refresh(link)
        self.assertEqual(link.receiver_id, receiver.id)
        self.assertIsNotNone(link.assigned_at)
        self.assertIsNone(link.notified_at)
        self.assertIn("@Santa", mock_reply.call_args.kwargs["text"])

    async def test_start_exchange_resumes_pending_delivery(self):
        _santa, _receiver, _group, link = await self._setup_delivery()
        update = self._make_update_mock(chat_type="group")
        update.effective_chat.get_member = AsyncMock(return_value=self._member("Receiver"))

        with patch.object(SantaBot, "is_update_expired", return_value=False):
            with patch.object(SantaBot, "send_message", new_callable=AsyncMock) as mock_send:
                with patch.object(SantaBot, "reply_message", new_callable=AsyncMock) as mock_reply:
                    await self.bot.start_exchange(update, Mock())

        self.bot.session.refresh(link)
        self.assertIsNotNone(link.notified_at)
        mock_send.assert_called_once()
        replies = [call.kwargs.get("text") for call in mock_reply.call_args_list]
        self.assertNotIn("The exchange has already been setup!", replies)

    async def test_start_exchange_reports_already_set_up_once_delivered(self):
        _santa, _receiver, _group, link = await self._setup_delivery()
        self.bot.exchange.mark_delivered(link)
        update = self._make_update_mock(chat_type="group")

        with patch.object(SantaBot, "is_update_expired", return_value=False):
            with patch.object(SantaBot, "send_message", new_callable=AsyncMock) as mock_send:
                with patch.object(SantaBot, "reply_message", new_callable=AsyncMock) as mock_reply:
                    await self.bot.start_exchange(update, Mock())

        mock_send.assert_not_called()
        mock_reply.assert_called_once_with(update=update, text="The exchange has already been setup!")

    async def test_reset_exchange_clears_delivery_state(self):
        _santa, _receiver, _group, link = await self._setup_delivery()
        self.bot.exchange.mark_delivered(link)
        update = self._make_update_mock(chat_type="group")

        with patch.object(SantaBot, "is_update_expired", return_value=False):
            with patch.object(SantaBot, "reply_message", new_callable=AsyncMock):
                await self.bot.reset_exchange(update, Mock())

        self.bot.session.refresh(link)
        self.assertIsNone(link.receiver_id)
        self.assertIsNone(link.assigned_at)
        self.assertIsNone(link.notified_at)
        self.assertEqual(self.bot.exchange.pending_deliveries(1), [])

    def test_assign_pairing_skips_santas_without_link(self):
        santa = Participant(telegram_id=10, telegram_username="Santa")
        receiver = Participant(telegram_id=20, telegram_username="Receiver")
        ghost = Participant(telegram_id=30, telegram_username="Ghost")
        group = Group(telegram_id=1)
        self.bot.session.add_all([santa, receiver, ghost, group])
        self.bot.session.commit()
        link = Link(santa_id=santa.id, group_id=group.id)
        self.bot.session.add(link)
        self.bot.session.commit()

        # ghost is in the pairing but has no links row: must be skipped, not raised
        self.bot.exchange.assign_pairing(1, {santa.id: receiver.id, ghost.id: receiver.id})

        self.bot.session.refresh(link)
        self.assertEqual(link.receiver_id, receiver.id)
        self.assertIsNotNone(link.assigned_at)
        self.assertIsNone(self.bot.session.scalars(select(Link).where(Link.santa_id == ghost.id)).first())

    @staticmethod
    def _member(name):
        member = AsyncMock()
        member.user.name = name
        return member

    async def test_membership_update_marks_the_group_as_left(self):
        await self._setup_group(1)
        update = Mock()
        update.my_chat_member = Mock()
        update.my_chat_member.chat.id = 1
        update.my_chat_member.new_chat_member.status = "left"
        await self.bot.bot_membership_changed(update, Mock())
        self.assertTrue(self.bot.exchange.group_is_orphaned(1))

    async def test_membership_update_clears_the_flag_when_readded(self):
        group = await self._setup_group(1)
        group.left_at = datetime.datetime(2026, 11, 23)
        self.bot.session.commit()
        update = Mock()
        update.my_chat_member = Mock()
        update.my_chat_member.chat.id = 1
        update.my_chat_member.new_chat_member.status = "member"
        await self.bot.bot_membership_changed(update, Mock())
        self.assertFalse(self.bot.exchange.group_is_orphaned(1))

    async def test_membership_update_ignores_other_transitions(self):
        await self._setup_group(1)
        update = Mock()
        update.my_chat_member = Mock()
        update.my_chat_member.chat.id = 1
        update.my_chat_member.new_chat_member.status = "restricted"
        await self.bot.bot_membership_changed(update, Mock())
        self.assertFalse(self.bot.exchange.group_is_orphaned(1))

    # -- log injection guards --

    async def test_message_body_cannot_forge_a_log_line(self):
        context = Mock()
        context.bot.send_message = AsyncMock(return_value=Mock(message_id=1))
        forged = "hello\n2026-11-23 04:00:00,000 INFO Sent Message fake delivery"
        with self.assertLogs(level="DEBUG") as captured:
            await SantaBot.send_message(context=context, chat_id=1, text=forged)
        body_lines = [line for line in captured.output if "Sent Message body" in line]
        self.assertEqual(len(body_lines), 1)
        self.assertIn("\\n", body_lines[0])
        self.assertNotIn("\n", body_lines[0].rstrip("\n"))

    async def test_message_body_is_absent_from_the_info_log(self):
        context = Mock()
        context.bot.send_message = AsyncMock(return_value=Mock(message_id=1))
        with self.assertLogs(level="INFO") as captured:
            await SantaBot.send_message(context=context, chat_id=1, text="a wizard hat")
        joined = "\n".join(captured.output)
        self.assertNotIn("wizard hat", joined)
        self.assertIn("Sent Message", joined)
        self.assertIn("chars", joined)

    async def test_incoming_command_is_logged_with_a_correlation_id(self):
        await self._setup_participant()
        update = self._make_update_mock()
        update.update_id = 4242
        update.effective_message.text = "/join"
        update.callback_query = None
        with self.assertLogs(level="INFO") as captured:
            await self.bot.observe_update(update, Mock())
        line = "\n".join(captured.output)
        self.assertIn("u4242", line)
        self.assertIn("command /join", line)
        self.assertIn("chat 1", line)
        self.assertIn("user 10", line)

    async def test_command_name_drops_the_bot_suffix(self):
        message = Mock()
        message.text = "/wish@SecretSantaBot"
        self.assertEqual(SantaBot.command_name(message), "/wish")

    async def test_command_name_ignores_plain_text(self):
        message = Mock()
        message.text = "123 Main Street, Springfield"
        self.assertEqual(SantaBot.command_name(message), "")
        self.assertEqual(SantaBot.command_name(None), "")

    async def test_incoming_plain_text_logs_no_body(self):
        await self._setup_participant()
        update = self._make_update_mock()
        update.update_id = 7
        update.effective_message.text = "123 Main Street, Springfield"
        update.callback_query = None
        with self.assertLogs(level="INFO") as captured:
            await self.bot.observe_update(update, Mock())
        line = "\n".join(captured.output)
        self.assertIn("command -", line)
        self.assertNotIn("Springfield", line)

    async def test_incoming_callback_query_logs_its_payload(self):
        update = MagicMock()
        update.update_id = 8
        update.effective_message = None
        update.effective_chat.id = 1
        update.effective_chat.type = "private"
        update.effective_user.id = 10
        update.callback_query.data = "cfg:addr:1"
        with self.assertLogs(level="INFO") as captured:
            await self.bot.observe_update(update, Mock())
        line = "\n".join(captured.output)
        self.assertIn("command -", line)
        self.assertIn("callback cfg:addr:1", line)

    async def test_handler_lines_are_tagged_with_the_update_they_belong_to(self):
        update = MagicMock()
        update.update_id = 99
        update.effective_message = None
        update.effective_chat = None
        update.effective_user = None
        update.callback_query = None

        formatter = logging.Formatter("[%(correlation_id)s] %(message)s")
        filter_ = CorrelationFilter()
        await self.bot.observe_update(update, Mock())
        record = logging.LogRecord("bot", logging.INFO, __file__, 1, "later line", None, None)
        filter_.filter(record)
        self.assertEqual(formatter.format(record), "[u99] later line")

    async def test_lines_outside_an_update_carry_a_placeholder(self):
        record = logging.LogRecord("bot", logging.INFO, __file__, 1, "startup", None, None)
        CorrelationFilter().filter(record)
        self.assertEqual(record.correlation_id, "-")

    async def test_display_name_cannot_forge_a_log_line(self):
        await self._setup_participant()
        update = self._make_update_mock()
        update.effective_user.name = "Eve\n2026-11-23 04:00:00,000 INFO Sent Message fake"
        with self.assertLogs(level="INFO") as captured:
            await self.bot.not_command(update, Mock())
        first = captured.output[0].rstrip("\n")
        self.assertNotIn("\n", first)
        self.assertIn("\\n", captured.output[0])

    # -- wishlist and settings handlers --

    def _make_callback_update(self, data, user_id=10, chat_id=1):
        update = Mock()
        update.effective_user.id = user_id
        update.effective_user.language_code = "en"
        query = AsyncMock()
        query.data = data
        query.message.chat.id = chat_id
        update.callback_query = query
        return update

    @patch.object(SantaBot, "reply_message")
    @patch.object(SantaBot, "is_update_expired")
    async def test_help_mentions_every_registered_command(self, mock_expired, mock_reply):
        from telegram.ext import CommandHandler

        mock_expired.return_value = False
        update = self._make_update_mock()
        await self.bot.help(update, Mock())
        text = mock_reply.call_args.kwargs["text"]

        commands = set()
        for handler in self.bot.handlers:
            if isinstance(handler, CommandHandler):
                commands |= set(handler.commands)
        self.assertTrue(commands)
        missing = sorted(f"/{command}" for command in commands if f"/{command}" not in text)
        self.assertEqual(missing, [], "commands registered but missing from /help")

    @patch.object(SantaBot, "reply_message")
    @patch.object(SantaBot, "is_update_expired")
    async def test_help_lists_the_new_commands(self, mock_expired, mock_reply):
        mock_expired.return_value = False
        update = self._make_update_mock()
        await self.bot.help(update, Mock())
        text = mock_reply.call_args.kwargs["text"]
        self.assertIn("/wish", text)
        self.assertIn("/settings", text)

    @patch.object(SantaBot, "reply_message")
    @patch.object(SantaBot, "send_message")
    @patch.object(SantaBot, "is_update_expired")
    async def test_wish_command_rejects_group_chat(self, mock_expired, mock_send, mock_reply):
        mock_expired.return_value = False
        update = self._make_update_mock(chat_type="group")
        await self.bot.wish_command(update, Mock(args=[]))
        mock_reply.assert_called_with(update=update, text="You must send me this in a private chat")

    @patch.object(SantaBot, "reply_message")
    @patch.object(SantaBot, "send_message")
    @patch.object(SantaBot, "is_update_expired")
    async def test_wish_command_without_joins(self, mock_expired, mock_send, mock_reply):
        mock_expired.return_value = False
        await self._setup_participant()
        update = self._make_update_mock(chat_type="private")
        await self.bot.wish_command(update, Mock(args=[]))
        text = mock_reply.call_args.kwargs["text"]
        self.assertIn("have not joined", text)

    @patch.object(SantaBot, "reply_message")
    @patch.object(SantaBot, "send_message")
    @patch.object(SantaBot, "is_update_expired")
    async def test_wish_command_single_group_shows_list(self, mock_expired, mock_send, mock_reply):
        mock_expired.return_value = False
        participant = await self._setup_participant()
        group = await self._setup_group(1)
        group.title = "Office"
        self.bot.session.commit()
        await self._setup_link(participant.id, group.id)
        update = self._make_update_mock(chat_type="private")
        await self.bot.wish_command(update, Mock(args=[]))
        text = mock_send.call_args.kwargs["text"]
        self.assertIn("Office", text)
        self.assertIn("empty", text)

    @patch.object(SantaBot, "reply_message")
    @patch.object(SantaBot, "send_message")
    @patch.object(SantaBot, "is_update_expired")
    async def test_wish_view_offers_share_button(self, mock_expired, mock_send, mock_reply):
        mock_expired.return_value = False
        participant = await self._setup_participant()
        group = await self._setup_group(1)
        await self._setup_link(participant.id, group.id)
        update = self._make_update_mock(chat_type="private")
        await self.bot.wish_command(update, Mock(args=[]))
        markup = mock_send.call_args.kwargs["reply_markup"]
        buttons = [button for row in markup.inline_keyboard for button in row]
        share = [button for button in buttons if button.switch_inline_query_current_chat is not None]
        self.assertEqual(len(share), 1)
        self.assertEqual(share[0].switch_inline_query_current_chat, "1")

    @patch.object(SantaBot, "reply_message")
    @patch.object(SantaBot, "send_message")
    @patch.object(SantaBot, "is_update_expired")
    async def test_wish_view_fetches_a_missing_group_title(self, mock_expired, mock_send, mock_reply):
        mock_expired.return_value = False
        participant = await self._setup_participant()
        group = await self._setup_group(1)
        await self._setup_link(participant.id, group.id)
        context = Mock()
        context.user_data = {}
        context.bot.get_chat = AsyncMock(return_value=Mock(title="Fetched Group"))
        update = self._make_update_mock(chat_type="private")
        await self.bot.wish_command(update, context)
        self.assertIn("Fetched Group", mock_send.call_args.kwargs["text"])
        self.assertEqual(self.bot.exchange.get_group(1).title, "Fetched Group")

    @patch.object(SantaBot, "reply_message")
    @patch.object(SantaBot, "send_message")
    @patch.object(SantaBot, "is_update_expired")
    async def test_wish_view_falls_back_when_the_title_cannot_be_read(self, mock_expired, mock_send, mock_reply):
        mock_expired.return_value = False
        participant = await self._setup_participant()
        group = await self._setup_group(1)
        await self._setup_link(participant.id, group.id)
        context = Mock()
        context.user_data = {}
        context.bot.get_chat = AsyncMock(side_effect=BadRequest("chat not found"))
        update = self._make_update_mock(chat_type="private")
        await self.bot.wish_command(update, context)
        self.assertIn("Exchange 1", mock_send.call_args.kwargs["text"])

    @patch.object(SantaBot, "reply_message")
    @patch.object(SantaBot, "send_message")
    @patch.object(SantaBot, "is_update_expired")
    async def test_wish_command_multiple_groups_shows_picker(self, mock_expired, mock_send, mock_reply):
        mock_expired.return_value = False
        participant = await self._setup_participant()
        for chat_id in (1, 2):
            group = await self._setup_group(chat_id)
            await self._setup_link(participant.id, group.id)
        update = self._make_update_mock(chat_type="private")
        await self.bot.wish_command(update, Mock(args=[]))
        markup = mock_send.call_args.kwargs["reply_markup"]
        buttons = [button for row in markup.inline_keyboard for button in row]
        self.assertEqual(len(buttons), 2)
        self.assertEqual({button.callback_data for button in buttons}, {"wish:1", "wish:2"})

    async def test_wish_callback_add_prompts_for_item(self):
        participant = await self._setup_participant()
        group = await self._setup_group(1)
        await self._setup_link(participant.id, group.id)
        update = self._make_callback_update("wishadd:1")
        context = Mock()
        context.user_data = {}
        with patch.object(SantaBot, "send_message", new_callable=AsyncMock) as mock_send:
            await self.bot.wish_callback(update, context)
        self.assertEqual(context.user_data["wishlist_target"], 1)
        self.assertIsInstance(mock_send.call_args.kwargs["reply_markup"], ForceReply)

    async def test_wishlist_input_adds_item(self):
        participant = await self._setup_participant()
        group = await self._setup_group(1)
        await self._setup_link(participant.id, group.id)
        self.bot.bot_id = 999
        update = self._make_update_mock(chat_type="private")
        update.effective_message.text = "a red scarf"
        update.effective_message.reply_to_message = Mock()
        update.effective_message.reply_to_message.from_user.id = 999
        context = Mock()
        context.user_data = {"wishlist_target": 1}
        with (
            patch.object(SantaBot, "reply_message", new_callable=AsyncMock) as mock_reply,
            patch.object(SantaBot, "send_message", new_callable=AsyncMock),
        ):
            await self.bot.wishlist_input(update, context)
        mock_reply.assert_called_with(update=update, text="Added.")
        items = self.bot.exchange.list_wishlist_items(participant.id, 1)
        self.assertEqual([item.details for item in items], ["a red scarf"])
        self.assertNotIn("wishlist_target", context.user_data)

    async def test_wishlist_input_ignores_reply_not_from_bot(self):
        participant = await self._setup_participant()
        group = await self._setup_group(1)
        await self._setup_link(participant.id, group.id)
        self.bot.bot_id = 999
        update = self._make_update_mock(chat_type="private")
        update.effective_message.text = "a red scarf"
        update.effective_message.reply_to_message = Mock()
        update.effective_message.reply_to_message.from_user.id = 12345
        context = Mock()
        context.user_data = {"wishlist_target": 1}
        with (
            patch.object(SantaBot, "reply_message", new_callable=AsyncMock),
            patch.object(SantaBot, "send_message", new_callable=AsyncMock),
        ):
            await self.bot.wishlist_input(update, context)
        self.assertEqual(self.bot.exchange.list_wishlist_items(participant.id, 1), [])

    @patch.object(SantaBot, "reply_message")
    @patch.object(SantaBot, "is_update_expired")
    async def test_settings_rejects_non_admin(self, mock_expired, mock_reply):
        mock_expired.return_value = False
        await self._setup_group(1)
        update = self._make_update_mock(chat_id=1)
        with patch.object(SantaBot, "is_group_admin", new_callable=AsyncMock, return_value=False):
            await self.bot.settings_command(update, Mock(args=[]))
        mock_reply.assert_called_with(update=update, text="Only group admins can change exchange settings.")

    @patch.object(SantaBot, "reply_message")
    @patch.object(SantaBot, "send_message")
    @patch.object(SantaBot, "is_update_expired")
    async def test_settings_shows_toggles_for_admin(self, mock_expired, mock_send, mock_reply):
        mock_expired.return_value = False
        await self._setup_group(1)
        update = self._make_update_mock(chat_id=1)
        with patch.object(SantaBot, "is_group_admin", new_callable=AsyncMock, return_value=True):
            await self.bot.settings_command(update, Mock(args=[]))
        markup = mock_send.call_args.kwargs["reply_markup"]
        callbacks = {button.callback_data for row in markup.inline_keyboard for button in row}
        self.assertEqual(callbacks, {"cfg:addr:1", "cfg:wish:1"})

    async def test_settings_callback_toggles_wishlist(self):
        await self._setup_group(1)
        update = self._make_callback_update("cfg:wish:1", chat_id=1)
        with patch.object(SantaBot, "is_group_admin", new_callable=AsyncMock, return_value=True):
            await self.bot.settings_callback(update, Mock())
        self.assertTrue(self.bot.exchange.group_options(1)["wishlist_enabled"])
        update.callback_query.edit_message_text.assert_awaited()

    async def test_settings_callback_rejects_non_admin(self):
        await self._setup_group(1)
        update = self._make_callback_update("cfg:wish:1", chat_id=1)
        with patch.object(SantaBot, "is_group_admin", new_callable=AsyncMock, return_value=False):
            await self.bot.settings_callback(update, Mock())
        self.assertFalse(self.bot.exchange.group_options(1)["wishlist_enabled"])
        update.callback_query.edit_message_text.assert_not_awaited()

    @patch.object(SantaBot, "reply_message")
    async def test_start_exchange_warns_about_missing_wishlists(self, mock_reply):
        santa = await self._setup_participant(10, "Santa")
        other = await self._setup_participant(20, "Other")
        group = await self._setup_group(1)
        await self._setup_link(santa.id, group.id)
        await self._setup_link(other.id, group.id)
        self.bot.exchange.set_group_option(1, wishlist_enabled=True)
        update = self._make_update_mock(chat_id=1)
        update.effective_chat.get_member = AsyncMock(return_value=Mock())
        await self.bot.start_exchange(update, Mock(args=[]))
        text = mock_reply.call_args.kwargs["text"]
        self.assertIn("no wishlist", text)
        self.assertIn("@Santa", text)
        link = self.bot.session.scalars(select(Link)).first()
        self.assertIsNone(link.receiver_id)

    @patch.object(SantaBot, "reply_message")
    async def test_start_exchange_confirm_bypasses_the_warning(self, mock_reply):
        santa = await self._setup_participant(10, "Santa")
        other = await self._setup_participant(20, "Other")
        group = await self._setup_group(1)
        await self._setup_link(santa.id, group.id)
        await self._setup_link(other.id, group.id)
        self.bot.exchange.set_group_option(1, wishlist_enabled=True)
        update = self._make_update_mock(chat_id=1)
        update.effective_chat.get_member = AsyncMock(return_value=Mock())
        with patch.object(SantaBot, "send_message", new_callable=AsyncMock):
            await self.bot.start_exchange(update, Mock(args=["confirm"]))
        links = list(self.bot.session.scalars(select(Link)).all())
        self.assertTrue(all(link.receiver_id is not None for link in links))

    async def test_delivery_includes_wishlist_when_enabled(self):
        _santa, receiver, group, link = await self._setup_delivery()
        await self._setup_link(receiver.id, group.id)
        self.bot.exchange.set_group_option(1, wishlist_enabled=True)
        self.assertEqual(self.bot.exchange.add_wishlist_item(receiver.id, 1, "a wizard hat"), "added")
        with patch.object(SantaBot, "send_message", new_callable=AsyncMock) as mock_send:
            delivered, _reason = await self.bot.send_individual_result(
                link, self._delivery_update(), Mock(), lambda s: s
            )
        self.assertTrue(delivered)
        self.assertIn("a wizard hat", mock_send.call_args.kwargs["text"])

    async def test_delivery_omits_wishlist_when_disabled(self):
        _santa, receiver, group, link = await self._setup_delivery()
        await self._setup_link(receiver.id, group.id)
        self.bot.exchange.add_wishlist_item(receiver.id, 1, "a wizard hat")
        with patch.object(SantaBot, "send_message", new_callable=AsyncMock) as mock_send:
            await self.bot.send_individual_result(link, self._delivery_update(), Mock(), lambda s: s)
        self.assertNotIn("wizard hat", mock_send.call_args.kwargs["text"])


class TestUpdateAgeLimit(MigratedDatabaseTestCase):
    """The stale-update guard must read its limit from config, not a magic 1 minute."""

    def test_default_limit_is_sixty_seconds(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("MESSAGE_MAX_AGE_SECONDS", None)
            self.assertEqual(SantaBot.resolve_max_message_age_seconds(), 60)
            self.assertEqual(self.bot.max_message_age_seconds, 60)

    def test_env_var_overrides_default(self) -> None:
        with patch.dict(os.environ, {"MESSAGE_MAX_AGE_SECONDS": "15"}):
            self.assertEqual(SantaBot.resolve_max_message_age_seconds(), 15)
            self.assertEqual(SantaBot(self.dbConnection).max_message_age_seconds, 15)

    def test_constructor_argument_wins_over_env_var(self) -> None:
        with patch.dict(os.environ, {"MESSAGE_MAX_AGE_SECONDS": "15"}):
            self.assertEqual(SantaBot.resolve_max_message_age_seconds(5), 5)
            self.assertEqual(SantaBot(self.dbConnection, max_message_age_seconds=5).max_message_age_seconds, 5)

    def test_invalid_env_var_falls_back_to_default(self) -> None:
        for raw in ("abc", "", "  ", "0", "-30"):
            with self.subTest(raw=raw):
                with patch.dict(os.environ, {"MESSAGE_MAX_AGE_SECONDS": raw}):
                    self.assertEqual(SantaBot.resolve_max_message_age_seconds(), 60)

    def test_update_within_limit_is_accepted(self) -> None:
        self.bot.max_message_age_seconds = 120
        update = MagicMock()
        update.effective_message.date = datetime.datetime.now(datetime.UTC) - datetime.timedelta(seconds=30)
        self.assertFalse(self.bot.is_update_expired(update))

    def test_update_past_limit_is_rejected(self) -> None:
        self.bot.max_message_age_seconds = 120
        update = MagicMock()
        update.effective_message.date = datetime.datetime.now(datetime.UTC) - datetime.timedelta(seconds=600)
        self.assertTrue(self.bot.is_update_expired(update))

    def test_unreadable_update_is_treated_as_expired(self) -> None:
        broken = MagicMock()
        broken.effective_message.date = None
        self.assertTrue(self.bot.is_update_expired(broken))

    def test_expired_update_logs_the_reason_and_context(self) -> None:
        self.bot.max_message_age_seconds = 120
        update = MagicMock()
        update.update_id = 4242
        update.effective_chat.id = -100123
        update.effective_user.id = 77
        update.effective_user.username = "tester"
        update.effective_message.text = "/join"
        update.effective_message.date = datetime.datetime.now(datetime.UTC) - datetime.timedelta(seconds=600)

        with self.assertLogs(level="WARNING") as captured:
            expired = self.bot.is_update_expired(update, handler_name="join")

        self.assertTrue(expired)
        line = "\n".join(captured.output)
        for expected in ("update 4242", "(join)", "chat -100123", "user 77", "@tester", "120s", "/join"):
            self.assertIn(expected, line)
        self.assertIn("expired", line)

    def test_fresh_update_logs_nothing(self) -> None:
        self.bot.max_message_age_seconds = 120
        update = MagicMock()
        update.effective_message.date = datetime.datetime.now(datetime.UTC) - datetime.timedelta(seconds=5)
        with self.assertNoLogs(level="WARNING"):
            self.assertFalse(self.bot.is_update_expired(update))

    def test_update_without_a_message_logs_why_it_was_dropped(self) -> None:
        update = MagicMock()
        update.effective_message = None
        with self.assertLogs(level="WARNING") as captured:
            self.assertTrue(self.bot.is_update_expired(update))
        self.assertIn("no message to age-check", "\n".join(captured.output))

    def test_unreadable_timestamp_logs_the_cause(self) -> None:
        update = MagicMock()
        update.effective_message.date = None
        with self.assertLogs(level="WARNING") as captured:
            self.assertTrue(self.bot.is_update_expired(update))
        self.assertIn("unreadable timestamp", "\n".join(captured.output))

    @patch.object(SantaBot, "reply_message")
    @patch.object(SantaBot, "is_update_expired", return_value=True)
    async def test_stale_update_never_reaches_handler_body(
        self, mock_expired: MagicMock, mock_reply: MagicMock
    ) -> None:
        update = MagicMock()
        update.effective_chat.id = 1
        update.effective_chat.type = "private"
        update.effective_user.id = 1
        await self.bot.start(update, Mock())
        mock_expired.assert_called_once_with(update, handler_name="start")
        mock_reply.assert_not_called()

    @patch.object(SantaBot, "reply_message")
    @patch.object(SantaBot, "is_update_expired", return_value=False)
    async def test_fresh_update_reaches_handler_body(self, mock_expired: MagicMock, mock_reply: MagicMock) -> None:
        update = MagicMock()
        update.effective_chat.id = 1
        update.effective_chat.type = "NotPrivate"
        update.effective_user.id = 1
        await self.bot.start(update, Mock())
        mock_reply.assert_called_with(update=update, text="You must send me this in a private chat")


class TestFeedbackHandler(MigratedDatabaseTestCase):
    """The /feedback command stores the text, then forwards it to the owner's chat."""

    def setUp(self) -> None:
        super().setUp()
        self.bot.feedback_chat_id = 999

    def _update(self, text="/feedback the status command said finished"):
        update = self._make_update_mock(chat_type="private")
        update.effective_message.text = text
        return update

    @patch.object(SantaBot, "reply_message")
    @patch.object(SantaBot, "send_message")
    @patch.object(SantaBot, "is_update_expired")
    async def test_feedback_is_stored_and_forwarded(self, mock_expired, mock_send, mock_reply):
        mock_expired.return_value = False
        await self.bot.feedback(self._update(), Mock())

        record = self.bot.session.scalars(select(Feedback)).one()
        self.assertEqual(record.body, "the status command said finished")
        self.assertEqual(record.telegram_id, 10)
        self.assertIsNotNone(record.forwarded_at)

        mock_send.assert_called_once()
        sent = mock_send.call_args.kwargs
        self.assertEqual(sent["chat_id"], 999)
        self.assertIn("the status command said finished", sent["text"])
        self.assertIn("@TestUser", sent["text"])
        self.assertEqual(mock_reply.call_args.kwargs["text"], "Thanks, I saved your feedback.")

    @patch.object(SantaBot, "reply_message")
    @patch.object(SantaBot, "send_message")
    @patch.object(SantaBot, "is_update_expired")
    async def test_feedback_without_inbox_is_stored_only(self, mock_expired, mock_send, mock_reply):
        mock_expired.return_value = False
        self.bot.feedback_chat_id = None
        await self.bot.feedback(self._update(), Mock())

        record = self.bot.session.scalars(select(Feedback)).one()
        self.assertEqual(record.body, "the status command said finished")
        self.assertIsNone(record.forwarded_at)
        mock_send.assert_not_called()
        self.assertEqual(mock_reply.call_args.kwargs["text"], "Thanks, I saved your feedback.")

    @patch.object(SantaBot, "reply_message")
    @patch.object(SantaBot, "send_message")
    @patch.object(SantaBot, "is_update_expired")
    async def test_feedback_without_body_explains_usage(self, mock_expired, mock_send, mock_reply):
        mock_expired.return_value = False
        await self.bot.feedback(self._update("/feedback"), Mock())

        self.assertEqual(self.bot.session.scalar(select(func.count()).select_from(Feedback)), 0)
        mock_send.assert_not_called()
        self.assertIn("/feedback <message>", mock_reply.call_args.kwargs["text"])

    @patch.object(SantaBot, "reply_message")
    @patch.object(SantaBot, "send_message")
    @patch.object(SantaBot, "is_update_expired")
    async def test_feedback_longer_than_a_telegram_message_is_rejected(self, mock_expired, mock_send, mock_reply):
        mock_expired.return_value = False
        await self.bot.feedback(self._update("/feedback " + "x" * 3501), Mock())

        self.assertEqual(self.bot.session.scalar(select(func.count()).select_from(Feedback)), 0)
        mock_send.assert_not_called()
        self.assertIn("3500", mock_reply.call_args.kwargs["text"])

    @patch.object(SantaBot, "reply_message")
    @patch.object(SantaBot, "send_message")
    @patch.object(SantaBot, "is_update_expired")
    async def test_failed_forward_keeps_the_feedback(self, mock_expired, mock_send, mock_reply):
        mock_expired.return_value = False
        mock_send.side_effect = Forbidden("bot was blocked by the user")
        await self.bot.feedback(self._update(), Mock())

        record = self.bot.session.scalars(select(Feedback)).one()
        self.assertEqual(record.body, "the status command said finished")
        self.assertIsNone(record.forwarded_at)
        self.assertEqual(mock_reply.call_args.kwargs["text"], "Thanks, I saved your feedback.")

    @patch.object(SantaBot, "reply_message")
    @patch.object(SantaBot, "send_message")
    @patch.object(SantaBot, "is_update_expired")
    async def test_feedback_keeps_newlines(self, mock_expired, mock_send, mock_reply):
        mock_expired.return_value = False
        await self.bot.feedback(self._update("/feedback first line\nsecond line"), Mock())

        record = self.bot.session.scalars(select(Feedback)).one()
        self.assertEqual(record.body, "first line\nsecond line")
