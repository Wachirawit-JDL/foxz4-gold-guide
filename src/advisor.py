from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Sequence

from .news_client import NewsMood
from .strategy import ema, rsi


Action = Literal["BUY", "SELL", "WAIT"]


@dataclass(frozen=True)
class TradePlan:
    action: Action
    confidence: int
    price: float
    entry_low: float | None
    entry_high: float | None
    stop_loss: float | None
    take_profit_1: float | None
    take_profit_2: float | None
    support: float
    resistance: float
    rsi: float
    atr: float
    technical_score: int
    total_score: int
    reasons: list[str]


def average_true_range(highs: Sequence[float], lows: Sequence[float], closes: Sequence[float], period: int = 14) -> float:
    if len(closes) < period + 1:
        raise ValueError("ข้อมูลไม่พอสำหรับ ATR")
    ranges = [
        max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1]))
        for i in range(1, len(closes))
    ]
    return sum(ranges[-period:]) / period


def build_trade_plan(
    highs: Sequence[float], lows: Sequence[float], closes: Sequence[float], news: NewsMood,
    fast_period: int = 9, slow_period: int = 21, rsi_period: int = 14,
) -> TradePlan:
    fast = ema(closes, fast_period)[-1]
    slow_values = ema(closes, slow_period)
    slow, previous_slow = slow_values[-1], slow_values[-2]
    strength = rsi(closes, rsi_period)[-1]
    if fast is None or slow is None or previous_slow is None or strength is None:
        raise ValueError("ข้อมูลไม่พอสำหรับวิเคราะห์")

    price = closes[-1]
    atr = average_true_range(highs, lows, closes)
    support, resistance = min(lows[-20:]), max(highs[-20:])
    technical = 0
    reasons: list[str] = []
    if fast > slow:
        technical += 2
        reasons.append("EMA9 อยู่เหนือ EMA21")
    else:
        technical -= 2
        reasons.append("EMA9 อยู่ต่ำกว่า EMA21")
    if slow > previous_slow:
        technical += 1
        reasons.append("แนวโน้มหลักกำลังยกตัว")
    elif slow < previous_slow:
        technical -= 1
        reasons.append("แนวโน้มหลักกำลังลดตัว")
    if 52 <= strength <= 68:
        technical += 1
        reasons.append("RSI สนับสนุนแรงซื้อ")
    elif 32 <= strength <= 48:
        technical -= 1
        reasons.append("RSI สนับสนุนแรงขาย")
    elif strength > 72:
        technical -= 1
        reasons.append("RSI สูง เสี่ยงไล่ราคา")
    elif strength < 28:
        technical += 1
        reasons.append("RSI ต่ำ เสี่ยงเกิดแรงเด้ง")

    total = technical + news.score
    conflict = technical * news.score < 0 and abs(news.score) >= 2
    if conflict:
        reasons.append("ข่าวกับกราฟขัดแย้งกัน")
    reasons.append(news.summary)
    action: Action = "WAIT"
    if not conflict and total >= 4 and strength < 72:
        action = "BUY"
    elif not conflict and total <= -4 and strength > 28:
        action = "SELL"
    confidence = min(85, 45 + abs(total) * 8)
    if action == "WAIT":
        return TradePlan(action, confidence, price, None, None, None, None, None, support, resistance, strength, atr, technical, total, reasons)
    if action == "BUY":
        entry_low, entry_high = price - 0.30 * atr, price + 0.10 * atr
        stop = min(support - 0.15 * atr, price - 1.50 * atr)
        tp1, tp2 = price + 1.50 * atr, price + 2.50 * atr
    else:
        entry_low, entry_high = price - 0.10 * atr, price + 0.30 * atr
        stop = max(resistance + 0.15 * atr, price + 1.50 * atr)
        tp1, tp2 = price - 1.50 * atr, price - 2.50 * atr
    return TradePlan(action, confidence, price, entry_low, entry_high, stop, tp1, tp2, support, resistance, strength, atr, technical, total, reasons)

