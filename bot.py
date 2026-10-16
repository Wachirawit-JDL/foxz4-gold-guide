from __future__ import annotations

import logging
import signal
import time
from datetime import datetime, timezone

from src.advisor import TradePlan, build_trade_plan
from src.commands import HELP_TEXT, parse_command
from src.config import Settings
from src.news_client import GlobalNewsClient, NewsMood
from src.telegram_client import TelegramClient
from src.yahoo_client import YahooGoldClient


LOG_FORMAT = "%(asctime)s | %(levelname)s | %(message)s"
logging.basicConfig(
    level=logging.INFO,
    format=LOG_FORMAT,
    handlers=[logging.StreamHandler(), logging.FileHandler("bot.log", encoding="utf-8")],
)
log = logging.getLogger("gold-guide-bot")
running = True
TRADINGVIEW_GC_URL = "https://www.tradingview.com/chart/?symbol=COMEX%3AGC1%21"
TRADINGVIEW_XAUUSD_URL = "https://www.tradingview.com/chart/?symbol=OANDA%3AXAUUSD"


def stop(*_: object) -> None:
    global running
    running = False


def _price(value: float | None) -> str:
    return "-" if value is None else f"{value:,.2f}"


def format_advice(settings: Settings, plan: TradePlan, news: NewsMood, bar_time: int) -> str:
    timestamp = datetime.fromtimestamp(bar_time, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    if plan.action == "BUY":
        title = "🟢 มุมมอง BUY — รอราคาเข้าโซน"
        levels = (
            f"โซนพิจารณาเข้า: {_price(plan.entry_low)}–{_price(plan.entry_high)}\n"
            f"จุดยอมแพ้ (SL): {_price(plan.stop_loss)}\n"
            f"แบ่งปิด TP1: {_price(plan.take_profit_1)}\n"
            f"เป้าหลัก TP2: {_price(plan.take_profit_2)}"
        )
    elif plan.action == "SELL":
        title = "🔴 มุมมอง SELL — รอราคาเข้าโซน"
        levels = (
            f"โซนพิจารณาเข้า: {_price(plan.entry_low)}–{_price(plan.entry_high)}\n"
            f"จุดยอมแพ้ (SL): {_price(plan.stop_loss)}\n"
            f"แบ่งปิด TP1: {_price(plan.take_profit_1)}\n"
            f"เป้าหลัก TP2: {_price(plan.take_profit_2)}"
        )
    else:
        title = "🟡 รอก่อน — ยังไม่ควรเปิดออเดอร์"
        levels = f"รอดูแนวรับ: {_price(plan.support)}\nรอดูแนวต้าน: {_price(plan.resistance)}"

    reasons = "\n".join(f"• {reason}" for reason in plan.reasons[:4])
    headlines = "\n".join(
        f"• [{item.category}] {item.title[:105]} ({item.domain})"
        for item in news.articles[:4]
    )
    risk = "\n⚠️ มีข่าวผลกระทบสูง ควรลดขนาดหรือรอความผันผวนสงบ" if news.high_impact else ""
    return (
        f"{title}\n\n"
        f"Gold Futures ({settings.symbol}) | {settings.timeframe}\n"
        f"ราคาปิดล่าสุด: {_price(plan.price)}\n"
        f"ความเชื่อมั่นเชิงระบบ: {plan.confidence}%\n\n"
        f"{levels}\n\n"
        f"RSI: {plan.rsi:.1f} | ATR: {plan.atr:.2f}\n"
        f"เหตุผล:\n{reasons}{risk}\n\n"
        f"ข่าวสำคัญที่ตรวจพบ:\n{headlines or '• ยังไม่พบหัวข้อเด่น'}\n\n"
        f"แท่งเวลา: {timestamp}\n"
        f"กราฟ TradingView: {TRADINGVIEW_GC_URL}\n"
        "หมายเหตุ: เป็นแนวทาง ไม่ใช่คำสั่งซื้อขาย และราคาอาจต่างจาก XAUUSD ของโบรกเกอร์"
    )


def format_news(news: NewsMood) -> str:
    if news.score >= 2:
        mood = "🟢 ภาพรวมข่าวเอนเอียงทางบวกต่อทอง"
    elif news.score <= -2:
        mood = "🔴 ภาพรวมข่าวเอนเอียงทางลบต่อทอง"
    else:
        mood = "🟡 ภาพรวมข่าวยังผสมกัน"
    headlines = "\n\n".join(
        f"• [{item.category}] {item.title[:135]}\n  {item.domain}\n  {item.url}"
        for item in news.articles[:8]
    )
    risk = "\n\n⚠️ พบหัวข้อข่าวผลกระทบสูง ตลาดอาจผันผวนมาก" if news.high_impact else ""
    return (
        f"📰 ข่าวที่อาจกระทบทอง\n\n{mood}\n{news.summary}{risk}\n\n"
        f"{headlines or 'ยังไม่พบข่าวเด่น'}\n\n"
        "หัวข้อข่าวคงภาษาต้นฉบับเพื่อป้องกันความหมายคลาดเคลื่อน"
    )


def format_chart() -> str:
    return (
        "📊 กราฟทองบน TradingView\n\n"
        f"Gold Futures ต่อเนื่อง (COMEX:GC1!):\n{TRADINGVIEW_GC_URL}\n\n"
        f"ทอง Spot (OANDA:XAUUSD):\n{TRADINGVIEW_XAUUSD_URL}\n\n"
        "บอทคำนวณสัญญาณจาก GC=F; ใช้ TradingView สำหรับเปิดดูและยืนยันกราฟด้วยตนเอง"
    )


def analyze_now(settings: Settings, market: YahooGoldClient, news_client: GlobalNewsClient) -> tuple[TradePlan, NewsMood, int]:
    count = max(settings.slow_ema, settings.rsi_period, 20) * 4 + 10
    bars = market.closed_bars(count)
    try:
        news = news_client.fetch()
    except Exception:
        log.exception("News fetch failed; using neutral news score")
        news = NewsMood(0, False, [], "ดึงข่าวไม่สำเร็จ จึงใช้กราฟเป็นหลัก")
    plan = build_trade_plan(
        bars.highs, bars.lows, bars.closes, news,
        settings.fast_ema, settings.slow_ema, settings.rsi_period,
    )
    return plan, news, bars.times[-1]


def main() -> None:
    settings = Settings.from_env()
    telegram = TelegramClient(settings.telegram_bot_token, settings.telegram_chat_id)
    market = YahooGoldClient(settings.symbol, settings.timeframe)
    news_client = GlobalNewsClient()
    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    telegram.set_commands()
    telegram.send(
        f"✅ Gold News Guide เริ่มทำงานแล้ว\n{settings.symbol} {settings.timeframe}\n"
        "วิเคราะห์กราฟ + ข่าวโลก และไม่เปิดออเดอร์แทนคุณ\nพิมพ์ /gold เพื่อวิเคราะห์ตอนนี้"
    )
    log.info("Gold news guide started: %s %s", settings.symbol, settings.timeframe)

    last_checked_bar: int | None = None
    last_action: str | None = None
    last_sent_price: float | None = None
    latest_plan: TradePlan | None = None
    latest_bar: int | None = None
    update_offset: int | None = None
    next_auto_check = 0.0
    try:
        while running:
            try:
                if time.monotonic() >= next_auto_check:
                    plan, news, bar_time = analyze_now(settings, market, news_client)
                    latest_plan, latest_bar = plan, bar_time
                    if bar_time != last_checked_bar:
                        last_checked_bar = bar_time
                        hourly_update = datetime.fromtimestamp(bar_time, tz=timezone.utc).minute == 0
                        price_moved = last_sent_price is None or abs(plan.price - last_sent_price) >= plan.atr * 0.5
                        if plan.action != last_action or price_moved or hourly_update:
                            telegram.send(format_advice(settings, plan, news, bar_time))
                            last_sent_price = plan.price
                        last_action = plan.action
                    next_auto_check = time.monotonic() + max(30, settings.check_interval_seconds)

                updates = telegram.get_updates(update_offset, timeout=10)
                for update in updates:
                    update_offset = int(update["update_id"]) + 1
                    message = update.get("message") or {}
                    chat = message.get("chat") or {}
                    if str(chat.get("id", "")) != settings.telegram_chat_id:
                        continue
                    command = parse_command(str(message.get("text", "")))
                    if command in {"start", "help"}:
                        telegram.send(HELP_TEXT)
                    elif command == "gold":
                        telegram.send("⏳ กำลังอ่านกราฟและข่าวล่าสุด กรุณารอสักครู่...")
                        plan, news, bar_time = analyze_now(settings, market, news_client)
                        latest_plan, latest_bar = plan, bar_time
                        telegram.send(format_advice(settings, plan, news, bar_time))
                    elif command == "news":
                        telegram.send("⏳ กำลังรวบรวมข่าวทั่วโลก...")
                        telegram.send(format_news(news_client.fetch()))
                    elif command == "chart":
                        telegram.send(format_chart())
                    elif command == "status":
                        if latest_plan is None or latest_bar is None:
                            telegram.send("✅ บอทออนไลน์ กำลังรอผลวิเคราะห์รอบแรก")
                        else:
                            checked = datetime.fromtimestamp(latest_bar, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
                            telegram.send(
                                f"✅ บอทออนไลน์\nตลาด: Gold Futures {settings.timeframe}\n"
                                f"มุมมองล่าสุด: {latest_plan.action}\nราคาล่าสุด: {_price(latest_plan.price)}\n"
                                f"แท่งที่วิเคราะห์: {checked}\nไม่มีการเปิดออเดอร์อัตโนมัติ"
                            )
                    else:
                        telegram.send("ไม่เข้าใจข้อความนี้ พิมพ์ /help เพื่อดูคำสั่งที่ใช้ได้")
            except Exception as exc:
                log.exception("Loop error")
                time.sleep(10)
    finally:
        log.info("Bot stopped")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        log.exception("Bot stopped because of a fatal error")
        raise
