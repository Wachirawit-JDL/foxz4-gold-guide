from __future__ import annotations


ALIASES = {
    "/start": "start",
    "/help": "help",
    "/gold": "gold",
    "/news": "news",
    "/chart": "chart",
    "/status": "status",
    "/paper": "paper",
    "/stats": "paper",
    "วิเคราะห์ทอง": "gold",
    "ดูทอง": "gold",
    "ทอง": "gold",
    "ข่าว": "news",
    "ข่าวทอง": "news",
    "กราฟ": "chart",
    "ดูกราฟ": "chart",
    "กราฟทอง": "chart",
    "สถานะ": "status",
    "ทดลอง": "paper",
    "สถิติ": "paper",
    "ช่วยเหลือ": "help",
}


def parse_command(text: str) -> str | None:
    normalized = " ".join(text.strip().lower().split())
    first = normalized.split(maxsplit=1)[0] if normalized else ""
    if first.startswith("/"):
        first = first.split("@", 1)[0]
        return ALIASES.get(first)
    return ALIASES.get(normalized)


HELP_TEXT = """🤖 วิธีใช้ Gold News Guide

/gold — วิเคราะห์กราฟและข่าว พร้อมโซนเข้า SL และ TP
/news — ดูข่าวล่าสุดที่อาจกระทบทอง
/chart — เปิดกราฟทองบน TradingView
/status — ดูสถานะระบบ
/paper — ดูออเดอร์ทดลองและสถิติ Win rate / ผลรวม R
/help — แสดงข้อความนี้

หรือพิมพ์: วิเคราะห์ทอง, ข่าวทอง, กราฟทอง, สถานะ, สถิติ

บอทให้ข้อมูลประกอบการตัดสินใจเท่านั้น ไม่เปิดออเดอร์และไม่รับประกันผลกำไร"""

