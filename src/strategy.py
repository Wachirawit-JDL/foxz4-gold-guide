from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Sequence


Side = Literal["BUY", "SELL"]


@dataclass(frozen=True)
class Signal:
    side: Side
    price: float
    rsi: float
    fast_ema: float
    slow_ema: float


def ema(values: Sequence[float], period: int) -> list[float | None]:
    if period < 1:
        raise ValueError("period must be positive")
    result: list[float | None] = [None] * len(values)
    if len(values) < period:
        return result
    seed = sum(values[:period]) / period
    result[period - 1] = seed
    multiplier = 2 / (period + 1)
    current = seed
    for index in range(period, len(values)):
        current = (values[index] - current) * multiplier + current
        result[index] = current
    return result


def rsi(values: Sequence[float], period: int) -> list[float | None]:
    result: list[float | None] = [None] * len(values)
    if len(values) <= period:
        return result
    changes = [values[i] - values[i - 1] for i in range(1, len(values))]
    avg_gain = sum(max(change, 0) for change in changes[:period]) / period
    avg_loss = sum(max(-change, 0) for change in changes[:period]) / period

    def score(gain: float, loss: float) -> float:
        if loss == 0:
            return 100.0 if gain > 0 else 50.0
        return 100 - (100 / (1 + gain / loss))

    result[period] = score(avg_gain, avg_loss)
    for index in range(period + 1, len(values)):
        change = changes[index - 1]
        avg_gain = (avg_gain * (period - 1) + max(change, 0)) / period
        avg_loss = (avg_loss * (period - 1) + max(-change, 0)) / period
        result[index] = score(avg_gain, avg_loss)
    return result


def generate_signal(
    closes: Sequence[float],
    fast_period: int,
    slow_period: int,
    rsi_period: int,
    rsi_buy_max: float,
    rsi_sell_min: float,
) -> Signal | None:
    if len(closes) < max(slow_period + 2, rsi_period + 2):
        return None
    fast = ema(closes, fast_period)
    slow = ema(closes, slow_period)
    strengths = rsi(closes, rsi_period)
    previous = (fast[-2], slow[-2])
    current = (fast[-1], slow[-1], strengths[-1])
    if any(value is None for value in (*previous, *current)):
        return None

    prev_fast, prev_slow = previous
    now_fast, now_slow, now_rsi = current
    assert prev_fast is not None and prev_slow is not None
    assert now_fast is not None and now_slow is not None and now_rsi is not None

    if prev_fast <= prev_slow and now_fast > now_slow and now_rsi <= rsi_buy_max:
        return Signal("BUY", closes[-1], now_rsi, now_fast, now_slow)
    if prev_fast >= prev_slow and now_fast < now_slow and now_rsi >= rsi_sell_min:
        return Signal("SELL", closes[-1], now_rsi, now_fast, now_slow)
    return None

