# Gold Chart → Telegram Guide Bot

บอท Python สำหรับอ่านกราฟทอง Spot (`XAU/USD`) จาก Twelve Data ตรวจเทียบราคากับ Alpha Vantage และส่งแนวทางไป Telegram โปรแกรมไม่มีความสามารถเปิดออเดอร์

## สิ่งที่ต้องมี

- Windows และ Python 3.10+
- Telegram bot token จาก `@BotFather` และ chat ID

## ติดตั้ง

### วิธีง่ายสำหรับผู้เริ่มต้น

ดับเบิลคลิก `SETUP_TELEGRAM.bat` แล้วทำตามข้อความในหน้าต่าง โปรแกรมจะตรวจ Token หา Chat ID และบันทึก `.env` ให้อัตโนมัติ หลังจากนั้นดับเบิลคลิก `START_BOT.bat` ไม่ต้องเปิดหรือล็อกอิน MT5

### วิธีใช้ PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

แก้ `.env` แล้วใส่ `TELEGRAM_BOT_TOKEN` และ `TELEGRAM_CHAT_ID` จากนั้นทดสอบในบัญชี Demo:

หากยังไม่รู้ chat ID ให้ใส่ token ก่อน กด Start และส่งข้อความหาบอท แล้วรัน:

```powershell
python tools/get_chat_id.py
```

นำเลขที่ได้ไปใส่ `TELEGRAM_CHAT_ID` แล้วจึงเริ่มบอท:

```powershell
python bot.py
```

## เงื่อนไขสัญญาณ

- BUY: EMA เร็วตัดขึ้น EMA ช้า และ RSI ไม่เกิน `RSI_BUY_MAX`
- SELL: EMA เร็วตัดลง EMA ช้า และ RSI ไม่น้อยกว่า `RSI_SELL_MIN`
- ประเมินเพียงครั้งเดียวเมื่อเกิดแท่งปิดใหม่

ราคาหลักมาจาก Twelve Data หากต่างจาก Alpha Vantage เกินเกณฑ์ บอทจะเปลี่ยนเป็น WAIT ราคาของโบรกเกอร์อาจต่างออกไป จึงใช้เป็นแนวทางเท่านั้น ไม่รับประกันผลกำไร

## ทำงานบนคลาวด์โดยไม่เปิดคอม

โปรเจกต์มี GitHub Actions ที่ `.github/workflows/gold-guide.yml` ตรวจทุก 15 นาที ให้เพิ่ม repository secrets ชื่อ `TELEGRAM_BOT_TOKEN` และ `TELEGRAM_CHAT_ID` แล้วเปิด Actions ระบบจะวิเคราะห์กราฟ ข่าวโลก แนวรับ/แนวต้าน และ ATR พร้อมส่งโซนเข้า, SL, TP1 และ TP2 เมื่อมุมมองเปลี่ยนหรือราคาเคลื่อนอย่างมีนัยสำคัญ

`render.yaml` สร้าง Render Web Service แผน Free สำหรับรับคำสั่ง Telegram ผ่าน webhook แม้ปิดคอม บริการฟรีอาจพักหลังไม่มีคำขอ 15 นาที คำสั่งแรกหลังพักจึงอาจตอบช้าประมาณหนึ่งนาที GitHub Actions จะทำหน้าที่วิเคราะห์ตามเวลา ส่วน Render จะตอบ `/gold`, `/news`, `/status` และ `/help`

## ทดสอบโค้ด

```powershell
python -m unittest discover -s tests -v
```
