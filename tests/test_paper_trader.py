import unittest

from src.advisor import TradePlan
from src.paper_trader import format_paper_stats, process_paper_trade


def plan(side="BUY"):
    if side == "BUY":
        levels = (100.0, 95.0, 105.0, 110.0)
    else:
        levels = (100.0, 105.0, 95.0, 90.0)
    entry, stop, tp1, tp2 = levels
    return TradePlan(side, 70, entry, 99, 101, stop, tp1, tp2, 90, 110, 55, 3, 4, 4, ["test"])


class PaperTraderTests(unittest.TestCase):
    def test_opens_and_reaches_two_targets(self):
        state = {}
        messages, changed = process_paper_trade(state, plan(), 1000, 101, 99)
        self.assertTrue(changed)
        self.assertIn("เปิดออเดอร์ทดลอง BUY", messages[0])

        messages, _ = process_paper_trade(state, plan(), 2000, 106, 99)
        self.assertIn("ถึง TP1", messages[0])
        self.assertTrue(state["paper"]["open"]["tp1_hit"])

        messages, _ = process_paper_trade(state, plan(), 3000, 111, 101)
        self.assertIn("ถึง TP1 และ TP2", messages[0])
        self.assertIsNone(state["paper"]["open"])
        self.assertGreater(state["paper"]["history"][0]["result_r"], 0)

    def test_same_candle_stop_and_target_is_counted_as_loss(self):
        state = {}
        process_paper_trade(state, plan(), 1000, 101, 99)
        process_paper_trade(state, plan(), 2000, 111, 94)
        self.assertEqual(state["paper"]["history"][0]["result_r"], -1.0)

    def test_tp1_then_breakeven_keeps_partial_profit(self):
        state = {}
        process_paper_trade(state, plan(), 1000, 101, 99)
        process_paper_trade(state, plan(), 2000, 106, 99)
        process_paper_trade(state, plan(), 3000, 103, 100)
        self.assertEqual(state["paper"]["history"][0]["result_r"], 0.5)
        self.assertIn("Win rate: 100.0%", format_paper_stats(state))


if __name__ == "__main__":
    unittest.main()
