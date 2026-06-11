# ---------------------------------------------------------
# FILE PATH: src/telegram_bot.py (v8.1 - Final Professional Version)
# ---------------------------------------------------------

import requests
import config
import os
import logging

# ایجاد یک سشن برای پایداری در شبکه و کاهش تأخیر
session = requests.Session()

def get_proxy():
    """دریافت تنظیمات پروکسی از فایل کانفیگ"""
    return getattr(config, 'PROXY', None)

def send_telegram_message(text):
    """تابع مرکزی و پایدار ارسال پیام به تلگرام"""
    token = os.environ.get("TELEGRAM_BOT_TOKEN") or getattr(config, 'TELEGRAM_BOT_TOKEN', None)
    chat_id = os.environ.get("TELEGRAM_CHAT_ID") or getattr(config, 'TELEGRAM_CHAT_ID', None)
    
    if not token or not chat_id: 
        logging.warning("توکن یا Chat ID تلگرام تنظیم نشده است.")
        return
        
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    
    try:
        proxy = get_proxy()
        response = session.post(url, json=payload, timeout=15, proxies={"https": proxy} if proxy else None)
        response.raise_for_status()
    except Exception as e:
        logging.error(f"خطای شبکه در ارسال به تلگرام: {e}")

def format_and_send_signal(signal_data):
    """💎 ارسال سیگنال هوشمند سیستم v8.0 با جزئیات کامل"""
    d = signal_data
    icon = "🟢 #LONG" if d['direction'] == "LONG" else "🔴 #SHORT"
    clean_pair = str(d.get('pair', 'UNKNOWN')).replace('_', '/')
    
    # محاسبه نسبت ریسک به پاداش (R:R Ratio)
    try:
        rr_ratio = round((d['tp2'] - d['entry_price']) / abs(d['entry_price'] - d['stop_loss']), 1)
    except:
        rr_ratio = 0
    
    message = (
        f"<b>{icon} سیگنال سیستم v8.0</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"🪙 <b>جفت ارز:</b> <code>{clean_pair}</code>\n"
        f"💵 <b>ورود:</b> <code>{d['entry_price']}</code>\n"
        f"🛑 <b>استاپ:</b> <code>{d['stop_loss']}</code>\n"
        f"🎯 <b>تارگت ۱:</b> <code>{d['tp1']}</code>\n"
        f"🎯 <b>تارگت ۲:</b> <code>{d['tp2']}</code>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"⚖️ <b>حجم پوزیشن:</b> <code>{d.get('position_size', 0)} USDT</code>\n"
        f"📊 <b>نسبت R:R:</b> <code>{rr_ratio}</code>\n"
        f"📈 <b>قدرت روند (ADX):</b> <code>{round(d.get('feat_adx', 0), 1)}</code>\n"
        f"🧠 <i>وضعیت: تایید شده توسط مدل اختصاصی {clean_pair}</i>"
    )
    send_telegram_message(message)

def send_heartbeat_report(watchlist_count, model_count):
    """گزارش سلامت سیستم (Heartbeat) برای اطمینان از زنده بودن ربات"""
    message = (
        f"🤖 <b>Status: System Online</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"🌐 <b>واچ‌لیست فعال:</b> <code>{watchlist_count} ارز</code>\n"
        f"🧠 <b>مدل‌های هوش مصنوعی فعال:</b> <code>{model_count}</code>\n"
        f"⏳ <b>وضعیت شبکه:</b> <code>Stable (OK)</code>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"<i>ربات در حال رصد دقیق بازار است...</i>"
    )
    send_telegram_message(message)
