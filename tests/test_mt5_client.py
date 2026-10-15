import unittest

import MetaTrader5 as mt5

from src.mt5_client import MT5Client


class MT5HelpersTests(unittest.TestCase):
    def test_volume_is_clamped_and_stepped_from_minimum(self):
        self.assertEqual(MT5Client._normalize_volume(0.26, 0.05, 1.0, 0.1), 0.25)
        self.assertEqual(MT5Client._normalize_volume(0.01, 0.05, 1.0, 0.1), 0.05)

    def test_market_execution_uses_allowed_ioc(self):
        selected = MT5Client._filling_type(mt5.SYMBOL_TRADE_EXECUTION_MARKET, 3)
        self.assertEqual(selected, mt5.ORDER_FILLING_IOC)

    def test_non_market_execution_uses_return(self):
        selected = MT5Client._filling_type(mt5.SYMBOL_TRADE_EXECUTION_INSTANT, 1)
        self.assertEqual(selected, mt5.ORDER_FILLING_RETURN)


if __name__ == "__main__":
    unittest.main()
