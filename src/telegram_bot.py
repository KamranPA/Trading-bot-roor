# ---------------------------------------------------------
# FILE NAME: telegram_bot.py
# ---------------------------------------------------------
import requests
import config
import os
import logging

session = requests.Session()

def send_telegram_message(text):
    token = os.environ.get("TELEGRAM_BOT_TOKEN") or getattr(config, 'TELEGRAM_BOT_TOKEN', None)
    chat_id = os.environ.get("TELEGRAM_CHAT_ID") or getattr(config, 'TELEGRAM_CHAT_ID', None)
    
    if not token or not chat_id: 
        logging.warning("توکن یا Chat ID تلگرام تنظیم نشده است.")
        return
        
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    
    try:
        proxy = getattr(config, 'PROXY', None)
        response = session.post(url, json=payload, timeout=15, proxies={"https": proxy} if proxy else None)
        response.raise_for_status()
    except Exception as e:
        logging.error(f"خطای تلگرام: {e}")

def send_optimization_report(params):
    """📢 ارسال گزارش خودکارِ ارتقای پارامترها به تلگرام"""
    message = (
        f"⚙️ <b>سیستم بهینه‌سازی هوشمند v7.1</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"✅ <b>پارامترهای جدید اعمال شدند:</b>\n\n"
        f"📊 <b>آستانه ADX:</b> <code>{params.get('adx_threshold')}</code>\n"
        f"🎯 <b>نسبت سود (TP):</b> <code>{params.get('tp_ratio')}</code>\n"
        f"🛡️ <b>نسبت ضرر (SL):</b> <code>{params.get('sl_ratio')}</code>\n\n"
        f"<i>ربات با تنظیمات جدید به فعالیت ادامه می‌دهد...</i>"
    )
    send_telegram_message(message)

def format_and_send_signal(signal_data):
    # ... (کد قبلی شما بدون تغییر باقی می‌ماند) ...
    pass
