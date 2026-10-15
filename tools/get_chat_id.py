from __future__ import annotations

import os

import requests
from dotenv import load_dotenv


def main() -> None:
    load_dotenv()
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise SystemExit("กรุณาใส่ TELEGRAM_BOT_TOKEN ในไฟล์ .env ก่อน")
    response = requests.get(
        f"https://api.telegram.org/bot{token}/getUpdates",
        timeout=15,
    )
    response.raise_for_status()
    updates = response.json().get("result", [])
    chats: dict[str, str] = {}
    for update in updates:
        message = update.get("message") or update.get("channel_post") or {}
        chat = message.get("chat") or {}
        if "id" in chat:
            name = chat.get("title") or chat.get("username") or chat.get("first_name") or "unknown"
            chats[str(chat["id"])] = str(name)
    if not chats:
        raise SystemExit("ยังไม่พบแชต กรุณากด Start และส่งข้อความหาบอท แล้วลองใหม่")
    print("พบ Telegram chat:")
    for chat_id, name in chats.items():
        print(f"  TELEGRAM_CHAT_ID={chat_id}  ({name})")


if __name__ == "__main__":
    main()

