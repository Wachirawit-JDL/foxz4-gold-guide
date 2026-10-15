from __future__ import annotations

import hmac
import os
import threading

from flask import Flask, abort, jsonify, request

from bot import analyze_now, format_advice, format_news
from src.commands import HELP_TEXT, parse_command
from src.config import Settings
from src.news_client import GlobalNewsClient
from src.telegram_client import TelegramClient
from src.yahoo_client import YahooGoldClient


app = Flask(__name__)
settings = Settings.from_env()
telegram = TelegramClient(settings.telegram_bot_token, settings.telegram_chat_id)
market = YahooGoldClient(settings.symbol, settings.timeframe)
news_client = GlobalNewsClient()
webhook_secret = os.environ["WEBHOOK_SECRET"]


def process_update(update: dict) -> None:
    message = update.get("message") or {}
    chat = message.get("chat") or {}
    if str(chat.get("id", "")) != settings.telegram_chat_id:
        return
    command = parse_command(str(message.get("text", "")))
    try:
        if command in {"start", "help"}:
            telegram.send(HELP_TEXT)
        elif command == "gold":
            telegram.send("⏳ กำลังอ่านกราฟและข่าวล่าสุด กรุณารอสักครู่...")
            plan, news, bar_time = analyze_now(settings, market, news_client)
            telegram.send(format_advice(settings, plan, news, bar_time))
        elif command == "news":
            telegram.send("⏳ กำลังรวบรวมข่าวทั่วโลก...")
            telegram.send(format_news(news_client.fetch()))
        elif command == "status":
            telegram.send(
                f"✅ บอทคลาวด์ออนไลน์\nตลาด: Gold Futures {settings.timeframe}\n"
                "แหล่งข้อมูล: Yahoo Finance + GDELT + ข่าวทางการ\n"
                "ไม่มีการเปิดออเดอร์อัตโนมัติ"
            )
        else:
            telegram.send("ไม่เข้าใจข้อความนี้ พิมพ์ /help เพื่อดูคำสั่งที่ใช้ได้")
    except Exception as exc:
        app.logger.exception("Command failed")
        telegram.send(f"⚠️ วิเคราะห์ไม่สำเร็จชั่วคราว: {exc}")


@app.get("/")
def health():
    return jsonify(status="ok", bot="gold-news-guide")


@app.post("/telegram")
def telegram_webhook():
    received = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if not hmac.compare_digest(received, webhook_secret):
        abort(403)
    update = request.get_json(silent=True)
    if not isinstance(update, dict):
        abort(400)
    threading.Thread(target=process_update, args=(update,), daemon=True).start()
    return jsonify(ok=True)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8000")))

