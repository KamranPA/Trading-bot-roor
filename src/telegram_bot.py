# ---------------------------------------------------------
# FILE PATH: /src/telegram_bot.py
# ---------------------------------------------------------

import requests
import config
import os
import sqlite3
import logging

# ایجاد یک سشن برای پایداری در شبکه
session = requests.Session()

def get_proxy():
    # اگر پروکسی دارید در config.py تعریف کنید
    return getattr(config, 'PROXY', None)

def send_telegram_message(text):
    token = os.environ.get("TELEGRAM_BOT_TOKEN") or getattr(config, 'TELEGRAM_BOT_TOKEN', None)
    chat_id = os.environ.get("TELEGRAM_CHAT_ID") or getattr(config, 'TELEGRAM_CHAT_ID', None)
    
    if not token or not chat_id: return
        
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    
    try:
        # اضافه کردن پروکسی برای پایداری در ایران
        proxy = get_proxy()
        response = session.post(url, json=payload, timeout=15, proxies={"https": proxy} if proxy else None)
        response.raise_for_status()
    except Exception as e:
        logging.error(f"خطای شبکه در ارسال به تلگرام: {e}")

def format_and_send_signal(signal_data):
    """💎 نمایش سیگنال ۹‌فیلتره"""
    d = signal_data
    icon = "🟢 #LONG" if d['direction'] == "LONG" else "🔴 #SHORT"
    clean_pair = str(d.get('pair', 'UNKNOWN')).replace('_', '/')
    
    # نمایش فیلترهای اصلی (به جای فیلتر حجم حذف شده)
    adx = round(d.get('feat_adx', 0), 1)
    rsi = round(d.get('feat_rsi', 0), 1)
    
    message = (
        f"<b>{icon} سیگنال هوشمند سیستم v7.1</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"🪙 <b>جفت ارز:</b> <code>{clean_pair}</code>\n"
        f"💵 <b>ورود:</b> <code>{d['entry_price']}</code>\n"
        f"🛡️ <b>استاپ:</b> <code>{d['stop_loss']}</code>\n"
        f"🎯 <b>تارگت ۱:</b> <code>{d['tp1']}</code>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"📈 <b>قدرت روند (ADX):</b> <code>{adx}</code>\n"
        f"⚖️ <b>شاخص RSI:</b> <code>{rsi}</code>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"🧠 <i>وضعیت: تایید شده توسط مدل هوش مصنوعی</i>"
    )
    send_telegram_message(message)

# بخش گزارش عملکرد (بدون تغییرات ساختاری، فقط تمیزکاری)
# ...
