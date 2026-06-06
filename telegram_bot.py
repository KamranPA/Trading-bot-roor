# src/telegram_bot.py
# نسخه نهایی v7.1 - مجهز به لایه بصری نمایش مدیریت سرمایه پویا و حجم‌گذاری ۳۶۰ درجه

import requests
import config

def send_telegram_message(text):
    """ارسال پیام متنی ساده به تلگرام با فعال بودن لایه توکن‌های امنیتی سیستم"""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", config.TELEGRAM_BOT_TOKEN)
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", config.TELEGRAM_CHAT_ID)
    
    if not token or not chat_id:
        print("⚠️ توکن تلگرام یا چت‌آیدی تنظیم نشده است. ارسال پیام لغو شد.")
        return
        
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown"
    }
    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code != 200:
            print(f"❌ خطا در ارسال تلگرام: {response.text}")
    except Exception as e:
        print(f"❌ خطای ارتباطی تلگرام: {e}")

def format_and_send_signal(signal_data):
    """💎 قالب‌بندی پیشرفته و ارسال سیگنال لایو همراه با پارامترهای مدیریت سرمایه پویا"""
    pair = signal_data['pair']
    symbol = pair.split('/')[0]
    direction = signal_data['direction']
    entry = signal_data['entry_price']
    sl = signal_data['stop_loss']
    tp1 = signal_data['tp1']
    tp2 = signal_data['tp2']
    
    # 💰 استخراج پارامترهای جدید مدیریت سرمایه پویا
    position_size = signal_data.get('position_size', 0.0)
    sl_percent = signal_data.get('sl_percent', 0.0)
    
    # انتخاب ایموجی بر اساس جهت بازار
    icon = "🟢 #LONG" if direction == "LONG" else "🔴 #SHORT"
    target_icon = "🏹" if direction == "LONG" else "🎯"
    
    # ساختاربندی پیام با رعایت خوانایی بالا و اعمال بولدینگ‌های استراتژیک
    message = (
        f"{icon} **سیگنال جدید دستیار هوشمند ۳۶۰ درجه**\n"
        f"━━━━━━━━━━━━━━━\n"
        f"🪙 **جفت ارز:** `{pair}`\n"
        f"🔮 **جهت ورود:** {direction}\n\n"
        f"💵 **نقطه ورود (Entry):** `{entry}`\n"
        f"🛡️ **حد ضرر (Stop Loss):** `{sl}` (Risk: {sl_percent}%)\n\n"
        f"{target_icon} **تارگت اول (TP1):** `{tp1}`\n"
        f"{target_icon} **تارگت دوم (TP2):** `{tp2}`\n"
        f"━━━━━━━━━━━━━━━\n"
        f"💰 **لایه مدیریت سرمایه پویا (Money Management):**\n"
        f"📊 **حجم پیشنهادی ورود:** `{position_size} USDT`\n"
        f"⚠️ **حداکثر خسارت در صورت استاپ:** `۱٪ از کل سرمایه`\n"
        f"━━━━━━━━━━━━━━━\n"
        f"📡 تایم‌فریم اسکن: {config.TIMEFRAME} | ربات نسخه v7.1"
    )
    
    send_telegram_message(message)
    print(f"🚀 سیگنال مدیریت‌شده‌ی {symbol} با موفقیت به تلگرام مخابره شد.")
