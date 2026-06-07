# ---------------------------------------------------------
# FILE PATH: /src/telegram_bot.py
# ---------------------------------------------------------
import requests
import config
import os

def send_telegram_message(text):
    # استفاده از مقادیر ایمن
    token = os.environ.get("TELEGRAM_BOT_TOKEN") or getattr(config, 'TELEGRAM_BOT_TOKEN', None)
    chat_id = os.environ.get("TELEGRAM_CHAT_ID") or getattr(config, 'TELEGRAM_CHAT_ID', None)
    
    if not token or not chat_id:
        return
        
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"❌ خطای تلگرام: {e}")

def format_and_send_signal(signal_data):
    """💎 نمایش ۱۰‌بعدی سیگنال: اضافه شدنِ نمایشِ تاییدیه حجم (Volume Confirmation)"""
    # استخراج داده‌ها
    d = signal_data
    
    # 🧠 تعیین وضعیت تاییدیه حجم برای نمایش بصری
    vol_status = "✅ تایید شد" if float(d.get('feat_vol_confirm', 0)) == 1.0 else "⚠️ ضعیف"
    
    icon = "🟢 #LONG" if d['direction'] == "LONG" else "🔴 #SHORT"
    
    message = (
        f"{icon} **سیگنال مدیریت‌شده ۱۰‌بعدی**\n"
        f"━━━━━━━━━━━━━━━\n"
        f"🪙 **جفت ارز:** `{d['pair']}`\n"
        f"🔮 **جهت:** `{d['direction']}`\n\n"
        f"💵 **ورود:** `{d['entry_price']}`\n"
        f"🛡️ **استاپ:** `{d['stop_loss']}`\n"
        f"🎯 **تارگت ۱:** `{d['tp1']}` | 🎯 **تارگت ۲:** `{d['tp2']}`\n"
        f"━━━━━━━━━━━━━━━\n"
        f"💰 **حجم ورود:** `{d['position_size']} USDT`\n"
        f"📊 **تاییدیه حجم (Vol Conf):** {vol_status}\n"
        f"📈 **قدرت روند (ADX):** `{round(d.get('feat_adx', 0), 1)}`\n"
        f"━━━━━━━━━━━━━━━\n"
        f"📡 `نسخه سیستم: v7.1`"
    )
    
    send_telegram_message(message)
