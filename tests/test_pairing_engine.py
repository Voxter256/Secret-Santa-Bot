import unittest

from bot.services.pairing_engine import PairingEngine


class TestPairingEngine(unittest.TestCase):
    """Pure unit tests — no DB, no mocking needed."""

    def setUp(self):
        self.engine = PairingEngine

    def test_simple_pairing_two(self):
        success, result = self.engine.find_combination([1, 2], [])
        self.assertTrue(success)
        self.assertEqual(len(result), 2)
        self.assertNotEqual(result[1], 1)
        self.assertNotEqual(result[2], 2)

    def test_three_participants(self):
        success, result = self.engine.find_combination([1, 2, 3], [])
        self.assertTrue(success)
        self.assertEqual(len(result), 3)
        for santa, receiver in result.items():
            self.assertNotEqual(santa, receiver)
        self.assertEqual(set(result.keys()), {1, 2, 3})
        self.assertEqual(set(result.values()), {1, 2, 3})

    def test_impossible_all_blocked(self):
        success, result = self.engine.find_combination([1, 2], [[1, 2]])
        self.assertFalse(success)
        self.assertEqual(result, {})

    def test_large_group(self):
        participants = list(range(1, 21))
        success, result = self.engine.find_combination(participants, [])
        self.assertTrue(success)
        self.assertEqual(len(result), 20)
        santas = set(result.keys())
        receivers = set(result.values())
        self.assertEqual(santas, set(participants))
        self.assertEqual(receivers, set(participants))
        for santa, receiver in result.items():
            self.assertNotEqual(santa, receiver)

    def test_single_participant_fails(self):
        success, result = self.engine.find_combination([1], [])
        self.assertFalse(success)
        self.assertEqual(result, {})

    def test_self_block_ignored(self):
        success, result = self.engine.find_combination([1, 2], [[1, 1]])
        self.assertTrue(success)
        self.assertEqual(len(result), 2)

    def test_get_random_pairing_direct(self):
        success, result = self.engine.get_random_pairing([(1, {2}), (2, {1})])
        self.assertTrue(success)
        self.assertEqual(result[1], 2)
        self.assertEqual(result[2], 1)

    def test_get_random_pairing_with_gifting(self):
        success, result = self.engine.get_random_pairing([(2, {3}), (3, {2})], gifting=[1])
        self.assertTrue(success)
        self.assertEqual(result[2], 3)
        self.assertEqual(result[3], 2)