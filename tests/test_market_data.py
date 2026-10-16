import time
import unittest
from unittest.mock import Mock, patch

from src.advisor import TradePlan
from src.market_data import (
    AlphaVantageGoldChecker,
    TwelveDataGoldClient,
    apply_price_check,
    check_price,
)


class MarketDataTests(unittest.TestCase):
    @patch("src.market_data.requests.get")
    def test_twelve_data_returns_only_closed_bars(self, get):
        now = int(time.time())
        closed = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(now - 1800))
        open_bar = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(now))
        response = Mock()
        response.json.return_value = {
            "values": [
                {"datetime": closed, "high": "2402", "low": "2390", "close": "2400"},
                {"datetime": open_bar, "high": "2410", "low": "2399", "close": "2408"},
            ]
        }
        response.raise_for_status.return_value = None
        get.return_value = response

        bars = TwelveDataGoldClient("secret", "XAU/USD", "M15").closed_bars(1)

        self.assertEqual(bars.closes, [2400.0])

    @patch("src.market_data.requests.get")
    def test_alpha_vantage_extracts_nested_price(self, get):
        response = Mock()
        response.json.return_value = {"data": {"symbol": "XAU", "spot_price": "2401.50"}}
        response.raise_for_status.return_value = None
        get.return_value = response
        self.assertEqual(AlphaVantageGoldChecker("secret").spot_price(), 2401.5)

    def test_divergent_price_forces_wait(self):
        checker = Mock()
        checker.spot_price.return_value = 2000.0
        result = check_price(2400.0, checker, 0.8)
        plan = TradePlan("BUY", 77, 2400, 2395, 2402, 2380, 2420, 2440, 2350, 2450, 55, 10, 4, 5, ["เดิม"])

        safe_plan = apply_price_check(plan, result)

        self.assertEqual(result.status, "divergent")
        self.assertEqual(safe_plan.action, "WAIT")
        self.assertIsNone(safe_plan.entry_low)


if __name__ == "__main__":
    unittest.main()
