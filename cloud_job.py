from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from bot import format_advice
from src.advisor import build_trade_plan
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


def main() -> None:
    settings = Settings.from_env()
    telegram = TelegramClient(settings.telegram_bot_token, settings.telegram_chat_id)
    market = YahooGoldClient(settings.symbol, settings.timeframe)
    count = max(settings.slow_ema, settings.rsi_period, 20) * 4 + 10
    bars = market.closed_bars(count)
    latest_bar = bars.times[-1]
    interval_seconds = INTERVALS[settings.timeframe][1]
    if int(time.time()) - latest_bar > interval_seconds * 3:
        print("Market has no recent closed bar; nothing to send")
        return

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
        print(f"No material change ({plan.action}); nothing sent")


if __name__ == "__main__":
    main()

