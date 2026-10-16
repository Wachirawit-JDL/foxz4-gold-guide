from __future__ import annotations

import os
import re
from dataclasses import dataclass

from dotenv import load_dotenv


def _as_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name, str(default)).strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} ต้องเป็น true หรือ false")


def _optional_int(name: str) -> int | None:
    value = os.getenv(name, "").strip()
    return int(value) if value else None


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str
    telegram_chat_id: str
    mt5_path: str | None
    mt5_login: int | None
    mt5_password: str | None
    mt5_server: str | None
    symbol: str
    market_symbol: str
    twelve_data_api_key: str
    alpha_vantage_api_key: str
    max_price_divergence_pct: float
    timeframe: str
    fast_ema: int
    slow_ema: int
    rsi_period: int
    rsi_buy_max: float
    rsi_sell_min: float
    check_interval_seconds: int
    auto_trade: bool
    lot_size: float
    stop_loss_points: int
    take_profit_points: int
    max_deviation_points: int
    magic_number: int

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()
        settings = cls(
            telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", "").strip(),
            telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID", "").strip(),
            mt5_path=os.getenv("MT5_PATH", "").strip() or None,
            mt5_login=_optional_int("MT5_LOGIN"),
            mt5_password=os.getenv("MT5_PASSWORD", "").strip() or None,
            mt5_server=os.getenv("MT5_SERVER", "").strip() or None,
            symbol=os.getenv("SYMBOL", "GC=F").strip().upper(),
            market_symbol=os.getenv("MARKET_SYMBOL", "XAU/USD").strip().upper(),
            twelve_data_api_key=os.getenv("TWELVE_DATA_API_KEY", "").strip(),
            alpha_vantage_api_key=os.getenv("ALPHA_VANTAGE_API_KEY", "").strip(),
            max_price_divergence_pct=float(os.getenv("MAX_PRICE_DIVERGENCE_PCT", "0.8")),
            timeframe=os.getenv("TIMEFRAME", "M15").strip().upper(),
            fast_ema=int(os.getenv("FAST_EMA", "9")),
            slow_ema=int(os.getenv("SLOW_EMA", "21")),
            rsi_period=int(os.getenv("RSI_PERIOD", "14")),
            rsi_buy_max=float(os.getenv("RSI_BUY_MAX", "70")),
            rsi_sell_min=float(os.getenv("RSI_SELL_MIN", "30")),
            check_interval_seconds=int(os.getenv("CHECK_INTERVAL_SECONDS", "10")),
            auto_trade=_as_bool("AUTO_TRADE"),
            lot_size=float(os.getenv("LOT_SIZE", "0.01")),
            stop_loss_points=int(os.getenv("STOP_LOSS_POINTS", "300")),
            take_profit_points=int(os.getenv("TAKE_PROFIT_POINTS", "600")),
            max_deviation_points=int(os.getenv("MAX_DEVIATION_POINTS", "20")),
            magic_number=int(os.getenv("MAGIC_NUMBER", "260101")),
        )
        settings.validate()
        return settings

    def validate(self) -> None:
        missing = []
        if not re.fullmatch(r"\d+:[A-Za-z0-9_-]{30,}", self.telegram_bot_token):
            missing.append("TELEGRAM_BOT_TOKEN")
        if not re.fullmatch(r"-?\d+", self.telegram_chat_id):
            missing.append("TELEGRAM_CHAT_ID")
        if missing:
            raise ValueError("กรุณาตั้งค่า " + ", ".join(missing) + " ในไฟล์ .env")
        if self.fast_ema >= self.slow_ema:
            raise ValueError("FAST_EMA ต้องน้อยกว่า SLOW_EMA")
        if min(self.fast_ema, self.slow_ema, self.rsi_period) < 2:
            raise ValueError("ช่วงคำนวณ indicator ต้องมีค่าอย่างน้อย 2")
        if self.lot_size <= 0:
            raise ValueError("LOT_SIZE ต้องมากกว่า 0")
        if self.max_price_divergence_pct <= 0:
            raise ValueError("MAX_PRICE_DIVERGENCE_PCT must be greater than 0")
        if self.check_interval_seconds < 1:
            raise ValueError("CHECK_INTERVAL_SECONDS ต้องมีค่าอย่างน้อย 1")

