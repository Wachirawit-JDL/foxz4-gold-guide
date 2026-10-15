@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Setup MT5 Telegram Guide Bot
python setup_gui.py
echo.
pause

