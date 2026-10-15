@echo off
chcp 65001 >nul
cd /d "%~dp0"
title MT5 Telegram Guide Bot
python bot.py
echo.
echo Bot stopped. Read the message above if there was an error.
pause

