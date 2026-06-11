import requests
import config
import os
import logging

session = requests.Session()

def get_proxy():
    return getattr(config, 'PROXY', None)

def send_telegram_message(text):
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
    """💎 نمایش سیگنال هوشمند v8.0 با جزئیات کامل"""
    d = signal_data
    icon = "🟢 #LONG" if d['direction'] == "LONG" else "🔴 #SHORT"
    clean_pair = str(d.get('pair', 'UNKNOWN')).replace('_', '/')
    
    # محاسبه ریسک به پاداش (R:R) برای دیدن کیفیت سیگنال
    rr_ratio = round((d['tp2'] - d['entry_price']) / abs(d['entry_price'] - d['stop_loss']), 1)
    
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
