from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from bot import format_advice, format_chart, format_news
from src.advisor import build_trade_plan
from src.commands import HELP_TEXT, parse_command
from src.config import Settings
from src.news_client import GlobalNewsClient, NewsMood
from src.telegram_client import TelegramClient
from src.yahoo_client import INTERVALS, YahooGoldClient


STATE_FILE = Path(".bot_state.json")


def load_state() -> dict:
    if not STATE_FILE.exists():
        return {}
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def handle_commands(
    telegram: TelegramClient,
    settings: Settings,
    plan,
    news: NewsMood,
    latest_bar: int,
    stale: bool,
    state: dict,
) -> bool:
    """Answer queued Telegram commands and persist the next update offset."""
    changed = False
    offset = state.get("update_offset")
    for update in telegram.get_updates(offset, timeout=0):
        state["update_offset"] = int(update["update_id"]) + 1
        changed = True
        message = update.get("message") or {}
        chat = message.get("chat") or {}
        if str(chat.get("id", "")) != settings.telegram_chat_id:
            continue
        command = parse_command(str(message.get("text", "")))
        if command in {"start", "help"}:
            telegram.send(HELP_TEXT + "\n\nโหมดฟรีบนคลาวด์อาจใช้เวลาตอบประมาณ 5 นาที")
        elif command == "gold":
            warning = "⚠️ ตลาดปิดหรือข้อมูลแท่งล่าสุดยังไม่อัปเดต\n\n" if stale else ""
            telegram.send(warning + format_advice(settings, plan, news, latest_bar))
        elif command == "news":
            telegram.send(format_news(news))
        elif command == "chart":
            telegram.send(format_chart())
        elif command == "status":
            checked = datetime.fromtimestamp(latest_bar, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
            telegram.send(
                "✅ บอทคลาวด์ออนไลน์ (ตรวจทุกประมาณ 5 นาที)\n"
                f"มุมมองล่าสุด: {plan.action}\n"
                f"ราคาล่าสุด: {plan.price:,.2f}\n"
                f"แท่งที่วิเคราะห์: {checked}\n"
                "ไม่มีการเปิดออเดอร์อัตโนมัติ"
            )
        else:
            telegram.send("ไม่เข้าใจข้อความนี้ พิมพ์ /help เพื่อดูคำสั่งที่ใช้ได้")
    return changed


def main() -> None:
    settings = Settings.from_env()
    telegram = TelegramClient(settings.telegram_bot_token, settings.telegram_chat_id)
    telegram.set_commands()
    market = YahooGoldClient(settings.symbol, settings.timeframe)
    count = max(settings.slow_ema, settings.rsi_period, 20) * 4 + 10
    bars = market.closed_bars(count)
    latest_bar = bars.times[-1]
    interval_seconds = INTERVALS[settings.timeframe][1]
    stale = int(time.time()) - latest_bar > interval_seconds * 3

    try:
        news = GlobalNewsClient().fetch()
    except Exception as exc:
        print(f"News unavailable, using neutral score: {exc}")
        news = NewsMood(0, False, [], "ดึงข่าวไม่สำเร็จ จึงใช้กราฟเป็นหลัก")
    plan = build_trade_plan(
        bars.highs, bars.lows, bars.closes, news,
        settings.fast_ema, settings.slow_ema, settings.rsi_period,
    )
    state = load_state()
    command_state_changed = handle_commands(
        telegram, settings, plan, news, latest_bar, stale, state,
    )
    if stale:
        if command_state_changed:
            save_state(state)
        print("Market has no recent closed bar; scheduled advice not sent")
        return

    manual = os.getenv("MANUAL_RUN", "false").lower() == "true"
    new_bar = state.get("last_bar") != latest_bar
    changed = state.get("last_action") != plan.action
    moved = abs(float(state.get("last_sent_price", plan.price)) - plan.price) >= plan.atr * 0.5
    hourly = datetime.fromtimestamp(latest_bar, tz=timezone.utc).minute == 0
    should_send = manual or (new_bar and (changed or moved or hourly))
    if should_send:
        telegram.send(format_advice(settings, plan, news, latest_bar))
        state.update({
            "last_bar": latest_bar,
            "last_action": plan.action,
            "last_sent_price": plan.price,
        })
        save_state(state)
        print(f"Sent {plan.action} advice")
    else:
        if command_state_changed:
            save_state(state)
        print(f"No material change ({plan.action}); nothing sent")


if __name__ == "__main__":
    main()

