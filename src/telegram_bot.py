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
    
    if not token or not chat_id: return
        
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    
    try:
        proxy = getattr(config, 'PROXY', None)
        session.post(url, json=payload, timeout=15, proxies={"https": proxy} if proxy else None)
    except Exception as e:
        logging.error(f"خطای شبکه در ارسال به تلگرام: {e}")

def format_and_send_signal(signal_data):
    """💎 گزارش کامل سیگنال با وضعیت فیلترهای استراتژی"""
    d = signal_data
    icon = "🟢 #LONG" if d['direction'] == "LONG" else "🔴 #SHORT"
    clean_pair = str(d.get('pair', 'UNKNOWN')).replace('_', '/')
    
    # بررسی وضعیت فیلترها (چک کردن منطق ۱۰ فاکتور)
    f_trend = "✅" if d.get('feat_trend_line') == 1 else "❌"
    f_adx = "✅" if d.get('feat_adx', 0) > config.ADX_THRESHOLD else "⚠️"
    f_rsi = "✅" if 40 < d.get('feat_rsi', 50) < 75 else "⚠️"
    
    message = (
        f"<b>{icon} سیگنال هوشمند سیستم v7.1</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"🪙 <b>جفت ارز:</b> <code>{clean_pair}</code>\n"
        f"💵 <b>ورود:</b> <code>{d['entry_price']}</code>\n"
        f"🛡️ <b>استاپ:</b> <code>{d['stop_loss']}</code>\n"
        f"🎯 <b>تارگت:</b> <code>{d['tp1']}</code>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"📊 <b>وضعیت فیلترهای استراتژی:</b>\n"
        f"{f_trend} روند کلی (EMA200)\n"
        f"{f_adx} قدرت روند (ADX: {round(d.get('feat_adx', 0), 1)})\n"
        f"{f_rsi} مومنتوم (RSI: {round(d.get('feat_rsi', 0), 1)})\n"
        f"━━━━━━━━━━━━━━━\n"
        f"🧠 <i>سیستم خود-بهینه‌ساز فعال است.</i>"
    )
    send_telegram_message(message)

def send_optimization_report(params):
    """📢 ارسال گزارش خودکارِ ارتقای پارامترها"""
    message = (
        f"⚙️ <b>سیستم بهینه‌سازی هوشمند v7.1</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"✅ <b>پارامترهای جدید اعمال شدند:</b>\n\n"
        f"📊 <b>آستانه ADX:</b> <code>{params.get('adx_threshold')}</code>\n"
        f"🎯 <b>ضریب سود (TP):</b> <code>{params.get('tp_ratio')}</code>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"<i>ربات با تنظیمات جدید بازنگری شد.</i>"
    )
    send_telegram_message(message)
