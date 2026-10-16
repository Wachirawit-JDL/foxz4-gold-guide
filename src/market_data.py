from __future__ import annotations

import math
import time
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Any

import requests

from .advisor import TradePlan


TIMEFRAME_SECONDS = {"M5": 300, "M15": 900, "M30": 1800, "H1": 3600}
TWELVE_INTERVALS = {"M5": "5min", "M15": "15min", "M30": "30min", "H1": "1h"}


@dataclass(frozen=True)
class BarData:
    times: list[int]
    highs: list[float]
    lows: list[float]
    closes: list[float]


@dataclass(frozen=True)
class PriceCheck:
    status: str  # ok, divergent, unavailable
    reference_price: float | None
    divergence_pct: float | None
    message: str


class TwelveDataGoldClient:
    """Closed XAU/USD candles from Twelve Data. API keys never enter errors."""

    endpoint = "https://api.twelvedata.com/time_series"

    def __init__(self, api_key: str, symbol: str, timeframe: str) -> None:
        if not api_key:
            raise ValueError("ยังไม่ได้ตั้งค่า TWELVE_DATA_API_KEY")
        if timeframe not in TWELVE_INTERVALS:
            raise ValueError("รองรับ TIMEFRAME: M5, M15, M30, H1")
        self.api_key = api_key
        self.symbol = symbol
        self.interval = TWELVE_INTERVALS[timeframe]
        self.seconds = TIMEFRAME_SECONDS[timeframe]

    def closed_bars(self, count: int) -> BarData:
        try:
            response = requests.get(
                self.endpoint,
                params={
                    "symbol": self.symbol,
                    "interval": self.interval,
                    "outputsize": count + 5,
                    "timezone": "UTC",
                    "order": "ASC",
                    "apikey": self.api_key,
                },
                timeout=25,
            )
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise RuntimeError("เชื่อมต่อ Twelve Data ไม่สำเร็จ") from exc

        values = payload.get("values") if isinstance(payload, dict) else None
        if not isinstance(values, list):
            raise RuntimeError("Twelve Data ไม่ส่งข้อมูลราคา XAU/USD กลับมา")

        now = int(time.time())
        rows: list[tuple[int, float, float, float]] = []
        for item in values:
            try:
                moment = datetime.fromisoformat(str(item["datetime"]).replace("Z", "+00:00"))
                if moment.tzinfo is None:
                    moment = moment.replace(tzinfo=timezone.utc)
                epoch = int(moment.timestamp())
                high, low, close = float(item["high"]), float(item["low"]), float(item["close"])
            except (KeyError, TypeError, ValueError, OverflowError):
                continue
            if epoch + self.seconds <= now and all(math.isfinite(value) for value in (high, low, close)):
                rows.append((epoch, high, low, close))

        rows = sorted(rows, key=lambda row: row[0])[-count:]
        if len(rows) < count:
            raise RuntimeError(f"ข้อมูลแท่งราคา XAU/USD ยังไม่พอ ({len(rows)}/{count})")
        return BarData(
            times=[row[0] for row in rows],
            highs=[row[1] for row in rows],
            lows=[row[2] for row in rows],
            closes=[row[3] for row in rows],
        )


class AlphaVantageGoldChecker:
    endpoint = "https://www.alphavantage.co/query"

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    def spot_price(self) -> float:
        if not self.api_key:
            raise RuntimeError("ยังไม่ได้ตั้งค่า ALPHA_VANTAGE_API_KEY")
        try:
            response = requests.get(
                self.endpoint,
                params={"function": "GOLD_SILVER_SPOT", "symbol": "XAU", "apikey": self.api_key},
                timeout=25,
            )
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise RuntimeError("เชื่อมต่อ Alpha Vantage ไม่สำเร็จ") from exc
        if not isinstance(payload, dict) or any(key in payload for key in ("Error Message", "Information", "Note")):
            raise RuntimeError("Alpha Vantage ยังไม่ส่งราคาทองกลับมา")
        price = _find_price(payload)
        if price is None:
            raise RuntimeError("อ่านราคาทองจาก Alpha Vantage ไม่สำเร็จ")
        return price


def _find_price(value: Any) -> float | None:
    if isinstance(value, dict):
        lowered = {str(key).lower().replace(" ", "_"): item for key, item in value.items()}
        for key in ("price", "spot_price", "price_usd", "value"):
            if key in lowered:
                try:
                    price = float(lowered[key])
                except (TypeError, ValueError):
                    pass
                else:
                    if math.isfinite(price) and price > 100:
                        return price
        for key, item in value.items():
            if "price" in str(key).lower():
                try:
                    price = float(item)
                except (TypeError, ValueError):
                    continue
                if math.isfinite(price) and price > 100:
                    return price
        for item in value.values():
            found = _find_price(item)
            if found is not None:
                return found
    elif isinstance(value, list):
        for item in value:
            found = _find_price(item)
            if found is not None:
                return found
    return None


def check_price(primary_price: float, checker: AlphaVantageGoldChecker, max_divergence_pct: float) -> PriceCheck:
    try:
        reference = checker.spot_price()
    except RuntimeError:
        return PriceCheck("unavailable", None, None, "Alpha Vantage ยังตรวจเทียบราคาไม่ได้ชั่วคราว")
    divergence = abs(primary_price - reference) / reference * 100
    if divergence > max_divergence_pct:
        return PriceCheck(
            "divergent",
            reference,
            divergence,
            f"ราคาสองแหล่งต่างกัน {divergence:.2f}% เกินเกณฑ์ {max_divergence_pct:.2f}%",
        )
    return PriceCheck("ok", reference, divergence, f"ราคาสองแหล่งใกล้กัน (ต่าง {divergence:.2f}%)")


def apply_price_check(plan: TradePlan, result: PriceCheck) -> TradePlan:
    if result.status != "divergent":
        return plan
    return replace(
        plan,
        action="WAIT",
        confidence=min(plan.confidence, 45),
        entry_low=None,
        entry_high=None,
        stop_loss=None,
        take_profit_1=None,
        take_profit_2=None,
        reasons=[result.message, *plan.reasons],
    )
