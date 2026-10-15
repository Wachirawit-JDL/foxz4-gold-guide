from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN

import MetaTrader5 as mt5

from .config import Settings
from .strategy import Side


TIMEFRAMES = {
    "M1": mt5.TIMEFRAME_M1,
    "M5": mt5.TIMEFRAME_M5,
    "M15": mt5.TIMEFRAME_M15,
    "M30": mt5.TIMEFRAME_M30,
    "H1": mt5.TIMEFRAME_H1,
    "H4": mt5.TIMEFRAME_H4,
    "D1": mt5.TIMEFRAME_D1,
}


@dataclass(frozen=True)
class BarData:
    times: list[int]
    closes: list[float]


class MT5Client:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def connect(self) -> None:
        kwargs: dict[str, object] = {}
        if self.settings.mt5_login is not None:
            kwargs["login"] = self.settings.mt5_login
        if self.settings.mt5_password:
            kwargs["password"] = self.settings.mt5_password
        if self.settings.mt5_server:
            kwargs["server"] = self.settings.mt5_server
        if self.settings.mt5_path:
            connected = mt5.initialize(self.settings.mt5_path, **kwargs)
        else:
            connected = mt5.initialize(**kwargs)
        if not connected:
            raise RuntimeError(f"เชื่อมต่อ MT5 ไม่สำเร็จ: {mt5.last_error()}")
        terminal = mt5.terminal_info()
        if terminal is None or not terminal.connected:
            raise RuntimeError("MT5 Terminal ยังไม่เชื่อมต่อกับโบรกเกอร์")
        if not mt5.symbol_select(self.settings.symbol, True):
            raise RuntimeError(f"ไม่พบ symbol {self.settings.symbol}: {mt5.last_error()}")

    def close(self) -> None:
        mt5.shutdown()

    def closed_bars(self, count: int) -> BarData:
        timeframe = TIMEFRAMES.get(self.settings.timeframe)
        if timeframe is None:
            raise ValueError(f"TIMEFRAME ไม่รองรับ: {self.settings.timeframe}")
        rates = mt5.copy_rates_from_pos(self.settings.symbol, timeframe, 1, count)
        if rates is None or len(rates) < count:
            raise RuntimeError(f"ข้อมูลแท่งราคาไม่พอ: {mt5.last_error()}")
        ordered = sorted(rates, key=lambda bar: int(bar["time"]))
        return BarData(
            times=[int(bar["time"]) for bar in ordered],
            closes=[float(bar["close"]) for bar in ordered],
        )

    def has_bot_position(self) -> bool:
        positions = mt5.positions_get(symbol=self.settings.symbol)
        return bool(positions and any(position.magic == self.settings.magic_number for position in positions))

    def place_market_order(self, side: Side) -> str:
        info = mt5.symbol_info(self.settings.symbol)
        tick = mt5.symbol_info_tick(self.settings.symbol)
        if info is None or tick is None:
            raise RuntimeError("อ่านราคา symbol จาก MT5 ไม่สำเร็จ")
        volume = self._normalize_volume(self.settings.lot_size, info.volume_min, info.volume_max, info.volume_step)
        is_buy = side == "BUY"
        price = float(tick.ask if is_buy else tick.bid)
        sl_distance = self.settings.stop_loss_points * info.point
        tp_distance = self.settings.take_profit_points * info.point
        minimum_stop = info.trade_stops_level * info.point
        if sl_distance < minimum_stop or tp_distance < minimum_stop:
            raise RuntimeError(
                f"SL/TP ใกล้ราคามากเกินไป: broker กำหนดขั้นต่ำ {info.trade_stops_level} points"
            )
        digits = info.digits
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": self.settings.symbol,
            "volume": volume,
            "type": mt5.ORDER_TYPE_BUY if is_buy else mt5.ORDER_TYPE_SELL,
            "price": price,
            "sl": round(price - sl_distance if is_buy else price + sl_distance, digits),
            "tp": round(price + tp_distance if is_buy else price - tp_distance, digits),
            "deviation": self.settings.max_deviation_points,
            "magic": self.settings.magic_number,
            "comment": "telegram-ema-rsi-bot",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": self._filling_type(info.trade_exemode, info.filling_mode),
        }
        check = mt5.order_check(request)
        if check is None or check.retcode != 0:
            detail = mt5.last_error() if check is None else f"{check.retcode}: {check.comment}"
            raise RuntimeError(f"ตรวจสอบคำสั่งไม่ผ่าน: {detail}")
        result = mt5.order_send(request)
        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            detail = mt5.last_error() if result is None else f"{result.retcode}: {result.comment}"
            raise RuntimeError(f"ส่งคำสั่งไม่สำเร็จ: {detail}")
        return f"ticket={result.order}, deal={result.deal}, price={result.price}"

    @staticmethod
    def _normalize_volume(value: float, minimum: float, maximum: float, step: float) -> float:
        low = Decimal(str(minimum))
        bounded = min(max(Decimal(str(value)), low), Decimal(str(maximum)))
        increment = Decimal(str(step))
        steps = ((bounded - low) / increment).to_integral_value(rounding=ROUND_DOWN)
        return float(low + steps * increment)

    @staticmethod
    def _filling_type(execution_mode: int, allowed_modes: int) -> int:
        # SYMBOL_FILLING_MODE is a bitmask, while ORDER_FILLING_* is an enum.
        # RETURN is valid except with Market Execution.
        if execution_mode != mt5.SYMBOL_TRADE_EXECUTION_MARKET:
            return mt5.ORDER_FILLING_RETURN
        if allowed_modes & 2:  # SYMBOL_FILLING_IOC
            return mt5.ORDER_FILLING_IOC
        if allowed_modes & 1:  # SYMBOL_FILLING_FOK
            return mt5.ORDER_FILLING_FOK
        raise RuntimeError("Symbol นี้ไม่มี filling mode สำหรับ market order")

