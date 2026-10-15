from __future__ import annotations

import re
import subprocess
import sys
import threading
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import messagebox

import requests

from setup_bot import latest_chat, set_env_values, telegram_get


ROOT = Path(__file__).resolve().parent
TOKEN_PATTERN = re.compile(r"^\d+:[A-Za-z0-9_-]{30,}$")


class SetupWindow(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("ตั้งค่า Gold Telegram Guide Bot")
        self.geometry("640x410")
        self.resizable(False, False)
        self.token = ""
        self.bot_username = ""

        tk.Label(self, text="ตั้งค่าบอทแจ้งแนวทางทองคำ", font=("Tahoma", 18, "bold")).pack(pady=(20, 8))
        tk.Label(
            self,
            text="1. ที่ BotFather ใช้ /revoke กับ Token เก่า แล้วขอ Token ใหม่\n2. วาง Token ใหม่ในช่องด้านล่าง (Token จะอยู่ในเครื่องนี้เท่านั้น)",
            font=("Tahoma", 11),
            justify="left",
        ).pack(pady=8)

        self.token_entry = tk.Entry(self, width=64, show="●", font=("Consolas", 11))
        self.token_entry.pack(pady=8)
        self.connect_button = tk.Button(
            self,
            text="เชื่อมต่อ Token",
            font=("Tahoma", 11, "bold"),
            width=25,
            command=self.connect_token,
        )
        self.connect_button.pack(pady=5)

        self.instructions = tk.Label(
            self,
            text="",
            font=("Tahoma", 11),
            fg="#174ea6",
            justify="center",
            wraplength=580,
        )
        self.instructions.pack(pady=10)
        self.finish_button = tk.Button(
            self,
            text="ฉันกด Start และส่ง hello แล้ว",
            font=("Tahoma", 11, "bold"),
            width=32,
            state="disabled",
            command=self.find_chat,
        )
        self.finish_button.pack(pady=5)
        self.status = tk.Label(self, text="รอ Token ใหม่", font=("Tahoma", 10), fg="#555555")
        self.status.pack(pady=12)

    def run_task(self, function) -> None:
        threading.Thread(target=function, daemon=True).start()

    def connect_token(self) -> None:
        token = self.token_entry.get().strip()
        if not TOKEN_PATTERN.fullmatch(token):
            messagebox.showerror("Token ไม่ถูกต้อง", "กรุณาคัดลอก Token ใหม่จาก BotFather ให้อยู่ในบรรทัดเดียว")
            return
        self.connect_button.config(state="disabled")
        self.status.config(text="กำลังตรวจ Token...", fg="#555555")

        def work() -> None:
            try:
                bot = telegram_get(token, "getMe")["result"]
            except Exception as exc:
                self.after(0, lambda: self.connection_failed(str(exc)))
                return
            self.token = token
            self.bot_username = str(bot["username"])
            self.after(0, self.connection_ready)

        self.run_task(work)

    def connection_failed(self, detail: str) -> None:
        self.connect_button.config(state="normal")
        self.status.config(text="เชื่อมต่อไม่สำเร็จ", fg="#b3261e")
        messagebox.showerror("เชื่อมต่อไม่สำเร็จ", detail)

    def connection_ready(self) -> None:
        self.status.config(text=f"Token ถูกต้อง: @{self.bot_username}", fg="#137333")
        self.instructions.config(
            text=f"กดลิงก์นี้ → t.me/{self.bot_username}\nกด Start แล้วส่งข้อความ hello จากนั้นกลับมากดปุ่มด้านล่าง",
            cursor="hand2",
        )
        self.instructions.bind("<Button-1>", lambda _: webbrowser.open(f"https://t.me/{self.bot_username}"))
        self.finish_button.config(state="normal")

    def find_chat(self) -> None:
        self.finish_button.config(state="disabled")
        self.status.config(text="กำลังค้นหา Chat ID...", fg="#555555")

        def work() -> None:
            try:
                chat = latest_chat(self.token)
                if not chat:
                    raise RuntimeError("ยังไม่พบข้อความ กรุณากด Start และส่ง hello ให้บอทก่อน")
                chat_id, chat_name = chat
                set_env_values(
                    {
                        "TELEGRAM_BOT_TOKEN": self.token,
                        "TELEGRAM_CHAT_ID": chat_id,
                        "SYMBOL": "GC=F",
                        "TIMEFRAME": "M15",
                        "AUTO_TRADE": "false",
                    }
                )
            except Exception as exc:
                self.after(0, lambda: self.chat_failed(str(exc)))
                return
            self.after(0, lambda: self.setup_complete(chat_name))

        self.run_task(work)

    def chat_failed(self, detail: str) -> None:
        self.finish_button.config(state="normal")
        self.status.config(text="ยังไม่พบ Chat ID", fg="#b3261e")
        messagebox.showerror("ยังตั้งค่าไม่สำเร็จ", detail)

    def setup_complete(self, chat_name: str) -> None:
        self.status.config(text="ตั้งค่าเสร็จแล้ว", fg="#137333")
        messagebox.showinfo(
            "สำเร็จ",
            f"เชื่อมต่อแชต {chat_name} แล้ว\nกำลังเปิดบอทกราฟทองคำ M15\nไม่มีการเปิดออเดอร์",
        )
        subprocess.Popen(
            [sys.executable, str(ROOT / "bot.py")],
            cwd=ROOT,
            creationflags=subprocess.CREATE_NEW_CONSOLE,
        )
        self.destroy()


if __name__ == "__main__":
    try:
        SetupWindow().mainloop()
    except requests.RequestException as exc:
        messagebox.showerror("Network error", str(exc))

