import unittest
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text

from bot._migrate import run_migrations
from bot.DBConnection import DBConnection
from bot.models.BlockedLink import BlockedLink
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


class TestSantaBot(MigratedDatabaseTestCase):
    @patch.object(SantaBot, "reply_message")
    @patch.object(SantaBot, "send_message")
    @patch.object(SantaBot, "checkUpdateAgeExpired")
    async def test_start(self, mock_expired: MagicMock, mock_send: MagicMock, mock_reply: MagicMock):
        await self.private_chat_required(mock_expired, mock_reply)

    @patch.object(SantaBot, "reply_message")
    @patch.object(SantaBot, "send_message")
    @patch.object(SantaBot, "checkUpdateAgeExpired")
    async def test_start_exchange_no_group_links(self, mock_expired: MagicMock, mock_send: MagicMock, mock_reply: MagicMock):
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

    def _make_update_mock(self, chat_id=1, user_id=10, username="TestUser",
                          chat_type="group", language_code="en", message_date=None):
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
            message_date = datetime.datetime.now(datetime.timezone.utc)
        update.effective_message.date = message_date
        update.effective_message.reply_to_message = None
        return update

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
    @patch.object(SantaBot, "checkUpdateAgeExpired")
    async def test_join_private_chat_rejected(self, mock_expired, mock_send, mock_reply):
        mock_expired.return_value = False
        update = self._make_update_mock(chat_type="private")
        context = Mock()
        await self.bot.join(update, context)
        mock_reply.assert_called_with(update=update, text="You must begin from a group chat")

    @patch.object(SantaBot, "reply_message")
    @patch.object(SantaBot, "send_message")
    @patch.object(SantaBot, "checkUpdateAgeExpired")
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
    @patch.object(SantaBot, "checkUpdateAgeExpired")
    async def test_join_no_address(self, mock_expired, mock_send, mock_reply):
        mock_expired.return_value = False
        p = Participant(telegram_id=10, telegram_username="TestUser", address=None)
        self.bot.session.add(p)
        self.bot.session.commit()
        update = self._make_update_mock()
        context = Mock()
        await self.bot.join(update, context)
        mock_reply.assert_called_with(update=update, text="I need your address first! I am sending you a private message now.")

    @patch.object(SantaBot, "reply_message")
    @patch.object(SantaBot, "send_message")
    @patch.object(SantaBot, "checkUpdateAgeExpired")
    async def test_join_no_group_hello(self, mock_expired, mock_send, mock_reply):
        mock_expired.return_value = False
        await self._setup_participant()
        update = self._make_update_mock()
        context = Mock()
        await self.bot.join(update, context)
        mock_reply.assert_called_with(update=update, text="Someone must say /hello first!")

    @patch.object(SantaBot, "reply_message")
    @patch.object(SantaBot, "send_message")
    @patch.object(SantaBot, "checkUpdateAgeExpired")
    async def test_join_success(self, mock_expired, mock_send, mock_reply):
        mock_expired.return_value = False
        await self._setup_participant()
        await self._setup_group()
        update = self._make_update_mock()
        context = Mock()
        await self.bot.join(update, context)
        mock_reply.assert_called_with(update=update, text="OK, you're in!")
        participant = self.bot.session.query(Participant).filter(Participant.telegram_id == 10).first()
        group = self.bot.session.query(Group).filter(Group.telegram_id == 1).first()
        link = self.bot.session.query(Link).filter(Link.santa_id == participant.id, Link.group_id == group.id).first()
        self.assertIsNotNone(link)

    @patch.object(SantaBot, "reply_message")
    @patch.object(SantaBot, "send_message")
    @patch.object(SantaBot, "checkUpdateAgeExpired")
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
    @patch.object(SantaBot, "checkUpdateAgeExpired")
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
    @patch.object(SantaBot, "checkUpdateAgeExpired")
    async def test_leave_success(self, mock_expired, mock_send, mock_reply):
        mock_expired.return_value = False
        p = await self._setup_participant()
        g = await self._setup_group()
        await self._setup_link(p.id, g.id)
        update = self._make_update_mock()
        context = Mock()
        await self.bot.leave(update, context)
        mock_reply.assert_called_with(update=update, text="Done.")
        link = self.bot.session.query(Link).filter(Link.santa_id == p.id).first()
        self.assertIsNone(link)

    # -- not_command handler tests --

    @patch.object(SantaBot, "reply_message")
    @patch.object(SantaBot, "send_message")
    @patch.object(SantaBot, "checkUpdateAgeExpired")
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
        blocked_link = self.bot.session.query(BlockedLink).filter(
            BlockedLink.participant_id == p.id,
            BlockedLink.blocked_username == "BlockedUser"
        ).first()
        self.assertIsNotNone(blocked_link)

    @patch.object(SantaBot, "reply_message")
    @patch.object(SantaBot, "send_message")
    @patch.object(SantaBot, "checkUpdateAgeExpired")
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
        blocked_link = self.bot.session.query(BlockedLink).filter(
            BlockedLink.participant_id == p1.id,
            BlockedLink.blocked_id == p2.id
        ).first()
        self.assertIsNotNone(blocked_link)
        mock_reply.assert_called_with(
            update=update,
            text="OK, you can no longer matched with that participant."
        )

    @patch.object(SantaBot, "reply_message")
    @patch.object(SantaBot, "send_message")
    @patch.object(SantaBot, "checkUpdateAgeExpired")
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
    @patch.object(SantaBot, "checkUpdateAgeExpired")
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
        blocked_link = self.bot.session.query(BlockedLink).filter(
            BlockedLink.participant_id == p.id,
            BlockedLink.blocked_username == "BlockedUser"
        ).first()
        self.assertIsNone(blocked_link)
        mock_reply.assert_called_with(
            update=update,
            text="You can now be assigned to @BlockedUser"
        )

    @patch.object(SantaBot, "reply_message")
    @patch.object(SantaBot, "send_message")
    @patch.object(SantaBot, "checkUpdateAgeExpired")
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
        mock_reply.assert_called_with(
            update=update,
            text="@BlockedUser was not blocked by you."
        )

    # -- status handler tests --

    @patch.object(SantaBot, "reply_message")
    @patch.object(SantaBot, "send_message")
    @patch.object(SantaBot, "checkUpdateAgeExpired")
    async def test_status_private_chat_rejected(self, mock_expired, mock_send, mock_reply):
        mock_expired.return_value = False
        update = self._make_update_mock(chat_type="private")
        context = Mock()
        await self.bot.status(update, context)
        mock_reply.assert_called_with(update=update, text="You must begin from a group chat")

    @patch.object(SantaBot, "reply_message")
    @patch.object(SantaBot, "send_message")
    @patch.object(SantaBot, "checkUpdateAgeExpired")
    async def test_status_no_group(self, mock_expired, mock_send, mock_reply):
        mock_expired.return_value = False
        update = self._make_update_mock()
        context = Mock()
        await self.bot.status(update, context)
        mock_reply.assert_called_with(update=update, text="Someone must say /hello first!")

    @patch.object(SantaBot, "reply_message")
    @patch.object(SantaBot, "send_message")
    @patch.object(SantaBot, "checkUpdateAgeExpired")
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
    @patch.object(SantaBot, "checkUpdateAgeExpired")
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

    # -- set_and_send_individual_result tests --

    async def test_set_and_send_individual_result_success(self):
        santa = Participant(telegram_id=10, telegram_username="Santa", address="North Pole")
        receiver = Participant(telegram_id=20, telegram_username="Receiver", address="Somewhere")
        self.bot.session.add(santa)
        self.bot.session.add(receiver)
        self.bot.session.commit()

        group = Group(telegram_id=1)
        self.bot.session.add(group)
        self.bot.session.commit()

        link = Link(santa_id=santa.id, group_id=group.id)
        self.bot.session.add(link)
        self.bot.session.commit()

        update = MagicMock()
        update.effective_chat.id = 1
        update.effective_chat.title = "Test Group"

        member_mock = AsyncMock()
        member_mock.user.name = "Receiver"
        update.effective_chat.get_member = AsyncMock(return_value=member_mock)

        context = Mock()
        gettext_mock = MagicMock(side_effect=lambda s: s)

        with patch.object(SantaBot, "send_message", new_callable=AsyncMock) as mock_send:
            with patch.object(SantaBot, "reply_message", new_callable=AsyncMock):
                success = await SantaBot.set_and_send_individual_result(
                    self.bot.session, update, context, santa.id, receiver.id, gettext_mock
                )

        self.assertTrue(success)
        self.bot.session.commit()
        self.bot.session.refresh(link)
        self.assertEqual(link.receiver_id, receiver.id)
        mock_send.assert_called_once()
        args, kwargs = mock_send.call_args
        self.assertEqual(kwargs["chat_id"], santa.telegram_id)
        self.assertIn("Receiver", kwargs["text"])

    async def test_set_and_send_individual_result_missing_participant(self):
        update = MagicMock()
        update.effective_chat.id = 1
        update.effective_chat.get_member = AsyncMock()
        context = Mock()
        gettext_mock = MagicMock(side_effect=lambda s: s)

        with patch.object(SantaBot, "send_message", new_callable=AsyncMock) as mock_send:
            with patch.object(SantaBot, "reply_message", new_callable=AsyncMock):
                success = await SantaBot.set_and_send_individual_result(
                    self.bot.session, update, context, 999, 888, gettext_mock
                )

        self.assertFalse(success)
        mock_send.assert_not_called()

    async def test_set_and_send_individual_result_get_member_fails(self):
        santa = Participant(telegram_id=10, telegram_username="Santa", address="North Pole")
        receiver = Participant(telegram_id=20, telegram_username="Receiver", address="Somewhere")
        self.bot.session.add(santa)
        self.bot.session.add(receiver)
        self.bot.session.commit()

        group = Group(telegram_id=1)
        self.bot.session.add(group)
        self.bot.session.commit()

        link = Link(santa_id=santa.id, group_id=group.id)
        self.bot.session.add(link)
        self.bot.session.commit()

        update = MagicMock()
        update.effective_chat.id = 1
        update.effective_chat.title = "Test Group"
        update.effective_chat.get_member = AsyncMock(side_effect=Exception("User not found"))

        context = Mock()
        gettext_mock = MagicMock(side_effect=lambda s: s)

        with patch.object(SantaBot, "send_message", new_callable=AsyncMock) as mock_send:
            with patch.object(SantaBot, "reply_message", new_callable=AsyncMock) as mock_reply:
                success = await SantaBot.set_and_send_individual_result(
                    self.bot.session, update, context, santa.id, receiver.id, gettext_mock
                )

        self.assertFalse(success)
        mock_send.assert_not_called()
        mock_reply.assert_called_once()
