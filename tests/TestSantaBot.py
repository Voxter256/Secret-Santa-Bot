import unittest

from bot.DBConnection import DBConnection
from bot.SantaBot import SantaBot
from unittest.mock import MagicMock, Mock, patch


class TestSantaBot(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        dbConnectionString = 'sqlite:///:memory:'
        cls.dbConnection = DBConnection(dbConnectionString)

        cls.bot = SantaBot(cls.dbConnection)

    @classmethod
    def setUp(cls) -> None:
        cls.dbConnection.createAll()

    @classmethod
    def tearDown(cls) -> None:
        cls.dbConnection.dropAll()

    @patch.object(SantaBot, 'reply_message')
    @patch.object(SantaBot, 'send_message')
    @patch.object(SantaBot, 'checkUpdateAgeExpired')
    def test_start(
        self,
        mock_expired: MagicMock,
        mock_send: MagicMock,
        mock_reply: MagicMock
    ):
        self.private_chat_required(mock_expired, mock_reply)

    @patch.object(SantaBot, 'reply_message')
    @patch.object(SantaBot, 'send_message')
    @patch.object(SantaBot, 'checkUpdateAgeExpired')
    def test_start_exchange_no_group_links(
        self,
        mock_expired: MagicMock,
        mock_send: MagicMock,
        mock_reply: MagicMock
    ):
        mock_expired.return_value = False
        context = Mock()
        update = MagicMock()
        update.effective_chat.id = 1
        self.bot.start_exchange(update, context)
        mock_reply.assert_called_with(
                update=update,
                text='No one has Joined!'
            )

    def private_chat_required(self, mock_expired, mock_reply):
        with self.subTest(private_chat_required=True):
            mock_expired.return_value = False
            context = Mock()
            update = MagicMock()
            update.effective_user.id = 1
            update.effective_user.username = 'Test'
            update.effective_chat.type = 'NotPrivate'
            self.bot.start(update, context)
            mock_reply.assert_called_with(
                update=update,
                text='You must send me this in a private chat'
            )
