from __future__ import annotations

import os

import requests

from src.config import Settings
from src.telegram_client import TelegramClient


def main() -> None:
    settings = Settings.from_env()
    public_url = os.environ["PUBLIC_BASE_URL"].rstrip("/")
    secret = os.environ["WEBHOOK_SECRET"]
    telegram = TelegramClient(settings.telegram_bot_token, settings.telegram_chat_id)
    response = requests.post(
        f"{telegram.base_url}/setWebhook",
        json={
            "url": f"{public_url}/telegram",
            "secret_token": secret,
            "allowed_updates": ["message"],
            "drop_pending_updates": False,
        },
        timeout=20,
    )
    response.raise_for_status()
    payload = response.json()
    if not payload.get("ok"):
        raise RuntimeError(payload)
    telegram.set_commands()
    telegram.send("✅ FoxZ4 Gold News Guide ย้ายขึ้นคลาวด์แล้ว สามารถปิดคอมได้\nพิมพ์ /gold เพื่อทดสอบ")
    print("Webhook configured successfully")


if __name__ == "__main__":
    main()

