from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .advisor import TradePlan


def _price(value: float) -> str:
    return f"{value:,.2f}"


def _time(epoch: int) -> str:
    return datetime.fromtimestamp(epoch, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _paper_state(state: dict[str, Any]) -> dict[str, Any]:
    paper = state.setdefault("paper", {})
    paper.setdefault("open", None)
    paper.setdefault("history", [])
    return paper


def _level_hit(side: str, high: float, low: float, level: float, kind: str) -> bool:
    if side == "BUY":
        return low <= level if kind == "stop" else high >= level
    return high >= level if kind == "stop" else low <= level


def _close_trade(paper: dict[str, Any], trade: dict[str, Any], bar_time: int, exit_price: float, result_r: float, reason: str) -> str:
    record = {
        **trade,
        "closed_bar": bar_time,
        "exit": exit_price,
        "result_r": round(result_r, 3),
        "result": "WIN" if result_r > 0.05 else "LOSS" if result_r < -0.05 else "BE",
        "close_reason": reason,
    }
    paper["history"].append(record)
    paper["history"] = paper["history"][-200:]
    paper["open"] = None
    icon = "✅" if record["result"] == "WIN" else "❌" if record["result"] == "LOSS" else "➖"
    return (
        f"{icon} ปิดออเดอร์ทดลอง {trade['side']} — {reason}\n"
        f"เข้า: {_price(trade['entry'])} | ออก: {_price(exit_price)}\n"
        f"ผลจำลอง: {result_r:+.2f}R\n"
        "เป็นการทดลองในบอท ไม่มีเงินจริงและไม่มีคำสั่งเข้า MT5"
    )


def process_paper_trade(
    state: dict[str, Any],
    plan: TradePlan,
    bar_time: int,
    bar_high: float,
    bar_low: float,
) -> tuple[list[str], bool]:
    """Update one simulated position using a conservative closed-candle model."""
    paper = _paper_state(state)
    before = repr(paper)
    messages: list[str] = []
    trade = paper.get("open")
    closed_this_bar = False

    if trade and bar_time > int(trade["opened_bar"]):
        side = str(trade["side"])
        stop = float(trade["stop_loss"])
        tp1 = float(trade["take_profit_1"])
        tp2 = float(trade["take_profit_2"])
        entry = float(trade["entry"])
        risk = float(trade["risk"])
        # If stop and target occur in the same candle, assume the stop happened first.
        if _level_hit(side, bar_high, bar_low, stop, "stop"):
            if trade.get("tp1_hit"):
                tp1_r = abs(tp1 - entry) / risk
                result_r = 0.5 * tp1_r
                reason = "ครึ่งแรกถึง TP1 และครึ่งหลังปิดที่จุดเข้า"
            else:
                result_r = -1.0
                reason = "ถึง SL"
            messages.append(_close_trade(paper, trade, bar_time, stop, result_r, reason))
            closed_this_bar = True
        elif _level_hit(side, bar_high, bar_low, tp2, "target"):
            tp1_r = abs(tp1 - entry) / risk
            tp2_r = abs(tp2 - entry) / risk
            result_r = 0.5 * tp1_r + 0.5 * tp2_r
            messages.append(_close_trade(paper, trade, bar_time, tp2, result_r, "ถึง TP1 และ TP2"))
            closed_this_bar = True
        elif not trade.get("tp1_hit") and _level_hit(side, bar_high, bar_low, tp1, "target"):
            trade["tp1_hit"] = True
            trade["stop_loss"] = entry
            messages.append(
                f"🎯 ออเดอร์ทดลอง {side} ถึง TP1 ที่ {_price(tp1)}\n"
                "จำลองปิดครึ่งหนึ่ง และเลื่อน SL ของส่วนที่เหลือมาที่จุดเข้า"
            )

    new_signal_bar = paper.get("last_signal_bar") != bar_time
    previous_action = paper.get("last_signal_action", "WAIT")
    if new_signal_bar:
        paper["last_signal_bar"] = bar_time
        paper["last_signal_action"] = plan.action

    can_open = (
        not closed_this_bar
        and paper.get("open") is None
        and new_signal_bar
        and plan.action in {"BUY", "SELL"}
        and plan.action != previous_action
        and all(
            value is not None
            for value in (plan.stop_loss, plan.take_profit_1, plan.take_profit_2)
        )
    )
    if can_open:
        assert plan.stop_loss is not None and plan.take_profit_1 is not None and plan.take_profit_2 is not None
        risk = abs(plan.price - plan.stop_loss)
        if risk > 0:
            trade = {
                "side": plan.action,
                "entry": plan.price,
                "stop_loss": plan.stop_loss,
                "original_stop_loss": plan.stop_loss,
                "take_profit_1": plan.take_profit_1,
                "take_profit_2": plan.take_profit_2,
                "risk": risk,
                "opened_bar": bar_time,
                "tp1_hit": False,
            }
            paper["open"] = trade
            messages.append(
                f"🧪 เปิดออเดอร์ทดลอง {plan.action}\n"
                f"Entry: {_price(plan.price)}\n"
                f"TP1: {_price(plan.take_profit_1)} | TP2: {_price(plan.take_profit_2)}\n"
                f"SL: {_price(plan.stop_loss)}\n"
                f"แท่งสัญญาณ: {_time(bar_time)}\n"
                "ไม่มีเงินจริงและไม่ได้ส่งคำสั่งเข้า MT5"
            )
    return messages, repr(paper) != before


def format_paper_stats(state: dict[str, Any]) -> str:
    paper = _paper_state(state)
    history = list(paper.get("history", []))
    wins = sum(float(item.get("result_r", 0)) > 0.05 for item in history)
    losses = sum(float(item.get("result_r", 0)) < -0.05 for item in history)
    breakeven = len(history) - wins - losses
    total_r = sum(float(item.get("result_r", 0)) for item in history)
    win_rate = wins / len(history) * 100 if history else 0.0

    current = paper.get("open")
    if current:
        open_text = (
            f"กำลังทดลอง: {current['side']} @ {_price(float(current['entry']))}\n"
            f"SL: {_price(float(current['stop_loss']))} | "
            f"TP1: {_price(float(current['take_profit_1']))} | TP2: {_price(float(current['take_profit_2']))}"
        )
    else:
        open_text = "กำลังทดลอง: ไม่มีออเดอร์เปิด"

    sample_note = (
        "ข้อมูลยังน้อย ควรรออย่างน้อย 30 ออเดอร์ก่อนประเมินระบบ"
        if len(history) < 30
        else "มีตัวอย่างอย่างน้อย 30 ออเดอร์แล้ว แต่ผลย้อนหลังไม่รับประกันอนาคต"
    )
    return (
        "📒 สถิติออเดอร์ทดลอง\n\n"
        f"{open_text}\n\n"
        f"ปิดแล้ว: {len(history)} ออเดอร์\n"
        f"ชนะ: {wins} | แพ้: {losses} | เสมอ: {breakeven}\n"
        f"Win rate: {win_rate:.1f}%\n"
        f"ผลรวม: {total_r:+.2f}R\n\n"
        f"{sample_note}\n"
        "สถิตินี้เป็นการจำลองจากแท่งราคาปิด ไม่รวม spread, slippage และค่าคอมมิชชัน"
    )
