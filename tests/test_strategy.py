import unittest

from src.strategy import ema, generate_signal, rsi


class IndicatorTests(unittest.TestCase):
    def test_ema_seed_and_progression(self):
        values = [1, 2, 3, 4, 5]
        self.assertEqual(ema(values, 3), [None, None, 2.0, 3.0, 4.0])

    def test_rsi_flat_market_is_neutral(self):
        values = [10.0] * 20
        scores = rsi(values, 14)
        self.assertEqual(scores[-1], 50.0)

    def test_signal_requires_enough_data(self):
        self.assertIsNone(generate_signal([1, 2, 3], 3, 5, 3, 70, 30))


if __name__ == "__main__":
    unittest.main()

