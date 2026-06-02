# src/telegram_bot.py
import os
import requests

def send_telegram_message(text):
    """ارسال پیام با لایه توزیع‌شده ضد فیلتر و استفاده از گیت‌هاب سکرتز"""
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')
    
    if not token or not chat_id:
        print("❌ خطا: متغیرهای محیطی تلگرام تنظیم نشده‌اند.")
        return False

    token = str(token).strip()
    chat_id = str(chat_id).strip()

    # لیست تانل‌های موازی شبکه برای تضمین پایداری ارسال
    urls = [
        f"https://api.telegram.org/bot{token}/sendMessage",
        f"https://teleapi.ir/bot{token}/sendMessage",
        f"https://api.telegram-proxy.org/bot{token}/sendMessage"
    ]
    
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown"
    }
    
    for url in urls:
        try:
            domain = url.split('/')[2]
            response = requests.post(url, json=payload, timeout=12)
            if response.status_code == 200:
                print(f"🚀 موفقیت‌آمیز: پیام از طریق تانل {domain} ارسال شد.")
                return True
            else:
                print(f"⚠️ تانل {domain} پاسخ خطا داد: {response.status_code}")
        except Exception as e:
            print(f"❌ خطای شبکه در تانل {domain}: {e}")
            
    return False

def format_and_send_signal(signal_data):
    """فرمت‌بندی پیشرفته فارسی برای سیگنال خروجی ربات"""
    if not signal_data:
        return False
        
    emoji_dir = "🟢 LONG (خرید)" if signal_data['direction'] == 'LONG' else "🔴 SHORT (فروش)"

    message = (
        f"🎯 **سیگنال جدید و زنده (ورود سریع)**\n\n"
        f"🔹 **جفت ارز:** {signal_data['pair']}\n"
        f"🔸 **موقعیت:** {emoji_dir}\n\n"
        f"💵 **نقطه ورود لایو:** {signal_data['entry_price']}\n"
        f"🛑 **حد ضرر (Stop Loss):** {signal_data['stop_loss']}\n"
        f"✅ **تارگت اول (TP1):** {signal_data['tp1']}\n"
        f"💎 **تارگت دوم (TP2):** {signal_data['tp2']}\n\n"
        f"📊 شاخص نوسان (ATR): {signal_data['atr_value']}\n"
        f"📈 قدرت روند واقعی (ADX): {signal_data['adx_value']}\n\n"
        f"✓ این موقعیت با فیلتر زمانی داینامیک ۸ ساعته محافظت شده است."
    )
    return send_telegram_message(message)
