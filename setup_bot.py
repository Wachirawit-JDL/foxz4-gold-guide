from __future__ import annotations

import getpass
import re
import sys
from pathlib import Path

import requests


ROOT = Path(__file__).resolve().parent
ENV_FILE = ROOT / ".env"
ENV_EXAMPLE = ROOT / ".env.example"
TOKEN_PATTERN = re.compile(r"^\d+:[A-Za-z0-9_-]{30,}$")


def telegram_get(token: str, method: str) -> dict:
    response = requests.get(
        f"https://api.telegram.org/bot{token}/{method}",
        timeout=20,
    )
    response.raise_for_status()
    payload = response.json()
    if not payload.get("ok"):
        raise RuntimeError(payload.get("description", "Telegram API error"))
    return payload


def latest_chat(token: str) -> tuple[str, str] | None:
    updates = telegram_get(token, "getUpdates").get("result", [])
    for update in reversed(updates):
        message = update.get("message") or update.get("channel_post") or {}
        chat = message.get("chat") or {}
        if "id" in chat:
            name = chat.get("title") or chat.get("username") or chat.get("first_name") or "Telegram user"
            return str(chat["id"]), str(name)
    return None


def set_env_values(values: dict[str, str]) -> None:
    source = ENV_FILE if ENV_FILE.exists() else ENV_EXAMPLE
    lines = source.read_text(encoding="utf-8-sig").splitlines()
    found: set[str] = set()
    output: list[str] = []
    for line in lines:
        match = re.match(r"^([A-Z0-9_]+)=", line)
        if match and match.group(1) in values:
            key = match.group(1)
            output.append(f"{key}={values[key]}")
            found.add(key)
        else:
            output.append(line)
    for key, value in values.items():
        if key not in found:
            output.append(f"{key}={value}")
    ENV_FILE.write_text("\n".join(output) + "\n", encoding="utf-8")


def main() -> None:
    print("=" * 58)
    print("ติดตั้ง MT5 Telegram Guide Bot")
    print("Token จะถูกเก็บใน .env บนเครื่องนี้เท่านั้น")
    print("=" * 58)
    print()
    print("สำคัญ: ใช้ Token ใหม่ที่ได้หลังจาก /revoke เท่านั้น")
    token = getpass.getpass("วาง Token ใหม่ แล้วกด Enter (ตัวอักษรจะไม่แสดง): ").strip()
    if not TOKEN_PATTERN.fullmatch(token):
        raise SystemExit("รูปแบบ Token ไม่ถูกต้อง กรุณารันใหม่และคัดลอก Token ให้ครบ")

    try:
        bot = telegram_get(token, "getMe")["result"]
    except Exception as exc:
        raise SystemExit(f"เชื่อม Telegram ไม่สำเร็จ: {exc}") from exc
    username = bot.get("username", "unknown_bot")
    print(f"\nเชื่อมต่อสำเร็จ: @{username}")
    print(f"1) เปิด https://t.me/{username}")
    print("2) กด Start")
    print("3) ส่งข้อความว่า hello ให้บอท")

    while True:
        input("\nทำครบแล้วกด Enter เพื่อค้นหา Chat ID...")
        try:
            chat = latest_chat(token)
        except Exception as exc:
            print(f"ยังเชื่อมไม่ได้: {exc}")
            continue
        if chat:
            chat_id, chat_name = chat
            break
        print("ยังไม่พบข้อความ กรุณากด Start และส่ง hello แล้วลองอีกครั้ง")

    set_env_values(
        {
            "TELEGRAM_BOT_TOKEN": token,
            "TELEGRAM_CHAT_ID": chat_id,
            "MT5_PATH": r"C:\Program Files\MetaTrader 5\terminal64.exe",
            "AUTO_TRADE": "false",
        }
    )
    print(f"\nตั้งค่าสำเร็จสำหรับแชต: {chat_name}")
    print("โหมด: แจ้งสัญญาณเท่านั้น (ไม่เปิดออเดอร์)")
    print("\nขั้นต่อไป:")
    print("1) เปิด MT5 และล็อกอินบัญชี")
    print("2) ดับเบิลคลิก START_BOT.bat")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit("\nยกเลิกการตั้งค่า")

