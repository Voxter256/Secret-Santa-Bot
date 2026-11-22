"""Message-catalog preloading and locale resolution."""

import unittest
from unittest.mock import MagicMock

import bot.SantaBot as santa_module
from bot.DBConnection import DBConnection
from bot.SantaBot import SantaBot


class TestTranslations(unittest.TestCase):
    def setUp(self):
        self.db = DBConnection("sqlite://")

    def _build_bot(self):
        real_translation = santa_module.translation
        calls = []

        def counting(*args, **kwargs):
            calls.append(kwargs.get("languages"))
            return real_translation(*args, **kwargs)

        santa_module.translation = counting
        self.addCleanup(setattr, santa_module, "translation", real_translation)
        return SantaBot(self.db), calls

    @staticmethod
    def _user(language_code):
        return MagicMock(language_code=language_code)

    def test_catalogs_load_once_at_construction(self):
        bot, calls = self._build_bot()
        self.assertEqual(len(calls), len(SantaBot.supported_languages))

        for _ in range(3):
            bot.gettext_translation(self._user("de"))

        self.assertEqual(len(calls), len(SantaBot.supported_languages))

    def test_locale_resolution_falls_back_to_english(self):
        bot, _calls = self._build_bot()
        cases = {
            "de": "Hallo",
            "ru": "Здравствуйте",
            "pt-BR": "Olá",
            "en": "Hello",
            "xx": "Hello",
            None: "Hello",
        }

        for language_code, expected in cases.items():
            translated = bot.gettext_translation(self._user(language_code))("Hello! Lets get you setup!")
            self.assertTrue(
                translated.startswith(expected),
                f"{language_code!r} resolved to {translated!r}",
            )

    def test_get_locality_normalizes_language_code(self):
        self.assertEqual(SantaBot.get_locality(self._user("PT-br")), "pt_br")
        self.assertEqual(SantaBot.get_locality(self._user("de")), "de")
        self.assertEqual(SantaBot.get_locality(self._user("xx")), "en")
        self.assertEqual(SantaBot.get_locality(self._user(None)), "en")
