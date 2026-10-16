from __future__ import annotations

import threading
import tkinter as tk
import webbrowser
from tkinter import messagebox

from setup_bot import set_env_values
from src.market_data import AlphaVantageGoldChecker, TwelveDataGoldClient


class MarketKeysWindow(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("เชื่อมแหล่งราคาทองฟรี")
        self.geometry("690x430")
        self.resizable(False, False)

        tk.Label(self, text="เชื่อมราคาทอง 2 แหล่ง", font=("Tahoma", 18, "bold")).pack(pady=(20, 6))
        tk.Label(
            self,
            text=(
                "ใช้ Twelve Data เป็นกราฟหลัก และ Alpha Vantage ตรวจเทียบราคา\n"
                "วาง API key ลงด้านล่าง ค่าเหล่านี้จะถูกซ่อนและไม่ถูกส่งเข้าแชต"
            ),
            font=("Tahoma", 11),
            justify="center",
        ).pack(pady=(0, 16))

        form = tk.Frame(self)
        form.pack(fill="x", padx=45)
        tk.Label(form, text="Twelve Data API key", font=("Tahoma", 11)).grid(row=0, column=0, sticky="w", pady=7)
        self.twelve_entry = tk.Entry(form, width=53, show="●", font=("Consolas", 11))
        self.twelve_entry.grid(row=0, column=1, padx=10)
        tk.Button(form, text="สมัคร/ดู key", command=lambda: webbrowser.open("https://twelvedata.com/account/api-keys")).grid(row=0, column=2)

        tk.Label(form, text="Alpha Vantage API key", font=("Tahoma", 11)).grid(row=1, column=0, sticky="w", pady=7)
        self.alpha_entry = tk.Entry(form, width=53, show="●", font=("Consolas", 11))
        self.alpha_entry.grid(row=1, column=1, padx=10)
        tk.Button(form, text="ขอ key ฟรี", command=lambda: webbrowser.open("https://www.alphavantage.co/support/#api-key")).grid(row=1, column=2)

        self.show_values = tk.BooleanVar(value=False)
        tk.Checkbutton(
            self,
            text="แสดงค่าที่กรอกชั่วคราว",
            variable=self.show_values,
            command=self.toggle_visibility,
            font=("Tahoma", 10),
        ).pack(pady=10)

        self.save_button = tk.Button(
            self,
            text="ตรวจสอบและเชื่อมต่อ",
            width=28,
            font=("Tahoma", 12, "bold"),
            command=self.start_validation,
        )
        self.save_button.pack(pady=8)
        self.status = tk.Label(self, text="รอ API key ทั้งสองตัว", font=("Tahoma", 10), fg="#555555")
        self.status.pack(pady=10)
        tk.Label(
            self,
            text="แผนฟรีอาจมีโควตารายวัน บอทจึงอ่านทุก 15 นาทีและไม่เปิดออเดอร์เอง",
            font=("Tahoma", 9),
            fg="#555555",
        ).pack(side="bottom", pady=18)

    def toggle_visibility(self) -> None:
        mask = "" if self.show_values.get() else "●"
        self.twelve_entry.config(show=mask)
        self.alpha_entry.config(show=mask)

    def start_validation(self) -> None:
        twelve_key = self.twelve_entry.get().strip()
        alpha_key = self.alpha_entry.get().strip()
        if not twelve_key or not alpha_key:
            messagebox.showerror("ข้อมูลไม่ครบ", "กรุณาใส่ API key ให้ครบทั้งสองช่อง")
            return
        self.save_button.config(state="disabled")
        self.status.config(text="กำลังตรวจ Twelve Data และ Alpha Vantage...", fg="#555555")
        threading.Thread(target=self.validate_and_save, args=(twelve_key, alpha_key), daemon=True).start()

    def validate_and_save(self, twelve_key: str, alpha_key: str) -> None:
        try:
            TwelveDataGoldClient(twelve_key, "XAU/USD", "M15").closed_bars(1)
        except Exception:
            self.after(0, lambda: self.failed("Twelve Data", "ตรวจ key ไม่ผ่าน กรุณาคัดลอกจากหน้า API Keys อีกครั้ง"))
            return
        try:
            AlphaVantageGoldChecker(alpha_key).spot_price()
        except Exception:
            self.after(0, lambda: self.failed("Alpha Vantage", "ตรวจ key ไม่ผ่าน หรือโควตาชั่วคราวยังไม่พร้อม"))
            return
        set_env_values(
            {
                "TWELVE_DATA_API_KEY": twelve_key,
                "ALPHA_VANTAGE_API_KEY": alpha_key,
                "MARKET_SYMBOL": "XAU/USD",
                "MAX_PRICE_DIVERGENCE_PCT": "0.8",
            }
        )
        self.after(0, self.complete)

    def failed(self, source: str, detail: str) -> None:
        self.save_button.config(state="normal")
        self.status.config(text=f"{source}: ยังเชื่อมต่อไม่สำเร็จ", fg="#b3261e")
        messagebox.showerror("เชื่อมต่อไม่สำเร็จ", detail)

    def complete(self) -> None:
        self.status.config(text="ตรวจสอบสำเร็จ ปิดหน้าต่างนี้ได้", fg="#137333")
        messagebox.showinfo("สำเร็จ", "บันทึก key ทั้งสองตัวอย่างปลอดภัยแล้ว\nกลับไปที่หน้าต่างแชตเพื่อให้อัปเดตบอทต่อ")
        self.destroy()


if __name__ == "__main__":
    MarketKeysWindow().mainloop()
