from __future__ import annotations

import requests


class TelegramClient:
    def __init__(self, token: str, chat_id: str) -> None:
        self.base_url = f"https://api.telegram.org/bot{token}"
        self.chat_id = chat_id

    def send(self, text: str) -> None:
        response = requests.post(
            f"{self.base_url}/sendMessage",
            json={"chat_id": self.chat_id, "text": text},
            timeout=15,
        )
        response.raise_for_status()
        payload = response.json()
        if not payload.get("ok"):
            raise RuntimeError(f"Telegram ปฏิเสธข้อความ: {payload}")

    def get_updates(self, offset: int | None = None, timeout: int = 10) -> list[dict]:
        params: dict[str, object] = {
            "timeout": timeout,
            "allowed_updates": '["message"]',
        }
        if offset is not None:
            params["offset"] = offset
        response = requests.get(
            f"{self.base_url}/getUpdates",
            params=params,
            timeout=timeout + 10,
        )
        response.raise_for_status()
        payload = response.json()
        if not payload.get("ok"):
            raise RuntimeError(f"Telegram อ่านข้อความไม่สำเร็จ: {payload}")
        return list(payload.get("result", []))

    def set_commands(self) -> None:
        commands = [
            {"command": "gold", "description": "วิเคราะห์ทอง พร้อมโซนเข้า SL และ TP"},
            {"command": "news", "description": "สรุปข่าวที่อาจกระทบทอง"},
            {"command": "status", "description": "ดูสถานะและเวลาวิเคราะห์ล่าสุด"},
            {"command": "help", "description": "ดูวิธีใช้บอท"},
        ]
        response = requests.post(
            f"{self.base_url}/setMyCommands",
            json={"commands": commands},
            timeout=15,
        )
        response.raise_for_status()
        if not response.json().get("ok"):
            raise RuntimeError("Telegram ตั้งค่าเมนูคำสั่งไม่สำเร็จ")


