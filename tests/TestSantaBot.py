import asyncio
import unittest
from unittest.mock import MagicMock, Mock, patch

from bot.DBConnection import DBConnection
from bot.SantaBot import SantaBot


class TestSantaBot(unittest.IsolatedAsyncioTestCase):

    @classmethod
    def setUpClass(cls) -> None:
        dbConnectionString = 'sqlite:///:memory:'
        cls.dbConnection = DBConnection(dbConnectionString)
        cls.bot = SantaBot(cls.dbConnection)

    def setUp(self) -> None:
        self.dbConnection.createAll()

    def tearDown(self) -> None:
        self.dbConnection.dropAll()

    @patch.object(SantaBot, 'reply_message')
    @patch.object(SantaBot, 'send_message')
    @patch.object(SantaBot, 'checkUpdateAgeExpired')
    async def test_start(
        self,
        mock_expired: MagicMock,
        mock_send: MagicMock,
        mock_reply: MagicMock
    ):
        await self.private_chat_required(mock_expired, mock_reply)

    @patch.object(SantaBot, 'reply_message')
    @patch.object(SantaBot, 'send_message')
    @patch.object(SantaBot, 'checkUpdateAgeExpired')
    async def test_start_exchange_no_group_links(
        self,
        mock_expired: MagicMock,
        mock_send: MagicMock,
        mock_reply: MagicMock
    ):
        mock_expired.return_value = False
        context = Mock()
        update = MagicMock()
        update.effective_chat.id = 1
        await self.bot.start_exchange(update, context)
        mock_reply.assert_called_with(
                update=update,
                text='No one has Joined!'
            )

    async def private_chat_required(self, mock_expired, mock_reply):
        with self.subTest(private_chat_required=True):
            mock_expired.return_value = False
            context = Mock()
            update = MagicMock()
            update.effective_user.id = 1
            update.effective_user.username = 'Test'
            update.effective_chat.type = 'NotPrivate'
            await self.bot.start(update, context)
            mock_reply.assert_called_with(
                update=update,
                text='You must send me this in a private chat'
            )