from __future__ import annotations

import math
import time
from dataclasses import dataclass

import yfinance as yf


INTERVALS = {
    "M5": ("5m", 5 * 60),
    "M15": ("15m", 15 * 60),
    "M30": ("30m", 30 * 60),
    "H1": ("60m", 60 * 60),
}


@dataclass(frozen=True)
class BarData:
    times: list[int]
    highs: list[float]
    lows: list[float]
    closes: list[float]


class YahooGoldClient:
    def __init__(self, symbol: str, timeframe: str) -> None:
        if timeframe not in INTERVALS:
            raise ValueError("Yahoo mode รองรับ TIMEFRAME: M5, M15, M30, H1")
        self.symbol = symbol
        self.interval, self.seconds = INTERVALS[timeframe]
        self.ticker = yf.Ticker(symbol)

    def closed_bars(self, count: int) -> BarData:
        frame = self.ticker.history(
            period="1mo",
            interval=self.interval,
            auto_adjust=False,
            actions=False,
            timeout=20,
        )
        if frame.empty or not {"High", "Low", "Close"}.issubset(frame.columns):
            raise RuntimeError("Yahoo Finance ไม่ส่งข้อมูลราคาทองคำกลับมา")
        now = int(time.time())
        rows: list[tuple[int, float, float, float]] = []
        for timestamp, values in frame[["High", "Low", "Close"]].iterrows():
            epoch = int(timestamp.timestamp())
            high, low, close = (float(values["High"]), float(values["Low"]), float(values["Close"]))
            if epoch + self.seconds <= now and all(math.isfinite(value) for value in (high, low, close)):
                rows.append((epoch, high, low, close))
        rows = rows[-count:]
        if len(rows) < count:
            raise RuntimeError(f"ข้อมูลแท่งราคายังไม่พอ ({len(rows)}/{count})")
        return BarData(
            times=[row[0] for row in rows],
            highs=[row[1] for row in rows],
            lows=[row[2] for row in rows],
            closes=[row[3] for row in rows],
        )

