import math
import unittest

from src.advisor import average_true_range, build_trade_plan
from src.news_client import NewsMood


class AdvisorTests(unittest.TestCase):
    def test_atr_is_positive(self):
        closes = [100 + i for i in range(20)]
        highs = [value + 2 for value in closes]
        lows = [value - 2 for value in closes]
        self.assertGreater(average_true_range(highs, lows, closes), 0)

    def test_uptrend_with_bullish_news_gives_buy_plan(self):
        closes = [100 + i * 0.08 + math.sin(i * 0.7) for i in range(80)]
        highs = [value + 1 for value in closes]
        lows = [value - 1 for value in closes]
        plan = build_trade_plan(highs, lows, closes, NewsMood(3, False, [], "ข่าวหนุนทอง"))
        self.assertEqual(plan.action, "BUY")
        self.assertLess(plan.stop_loss, plan.price)
        self.assertGreater(plan.take_profit_1, plan.price)

    def test_conflicting_news_forces_wait(self):
        closes = [100 + i * 0.5 for i in range(80)]
        highs = [value + 1 for value in closes]
        lows = [value - 1 for value in closes]
        plan = build_trade_plan(highs, lows, closes, NewsMood(-3, True, [], "ข่าวกดดันทอง"))
        self.assertEqual(plan.action, "WAIT")


if __name__ == "__main__":
    unittest.main()
