# src/telegram_bot.py
# ماژول فرمت‌بندی و ارسال سیگنال‌ها به تلگرام

import requests

# این دو متغیر در فاز نهایی برای امنیت بیشتر به GitHub Secrets منتقل می‌شوند
# فعلاً برای تست، مقادیر دریافتی از تلگرام را جایگزین کنید
TELEGRAM_TOKEN = "8205878716:AAFOSGnsF1gnY3kww1WvPT0HYubCkyPaC64"
TELEGRAM_CHAT_ID = "104506829" # مثلاً @MyChannelId

def send_telegram_message(text):
    """تابع پایه برای ارسال متن به تلگرام از طریق متد API"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown" # برای پشتیبانی از بولد (Bold) کردن متون
    }
    try:
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            return True
        else:
            print(f"خطا در ارسال تلگرام: {response.text}")
            return False
    except Exception as e:
        print(f"خطای شبکه در ارسال تلگرام: {e}")
        return False

def format_and_send_signal(signal_data):
    """تبدیل اطلاعات سیگنال به یک قالب پیام فارسی و شیک و ارسال آن"""
    if signal_data is None:
        return False
        
    # تشخیص ایموجی و رنگ بر اساس جهت معامله
    if signal_data['direction'] == 'LONG':
        emoji_dir = "🟢 #LONG (خرید)"
    else:
        emoji_dir = "🔴 #SHORT (فروش)"

    # ساخت قالب متن پیام با استفاده از مشخصات سیگنال
    message = (
        f"📊 **سیگنال جدید سیستم هوشمند**\n"
        f"━━━━━━━━━━━━━━━\n"
        f"🪙 **جفت‌ارز:** {signal_data['pair']}\n"
        f"📈 **جهت پوزیشن:** {emoji_dir}\n\n"
        f"🎯 **نقطه ورود (Entry):** {signal_data['entry_price']}\n"
        f"🛑 **حد ضرر (Stop Loss):** {signal_data['stop_loss']}\n\n"
        f"🎯 **حد سود اول (TP1):** {signal_data['tp1']} (ریوارد ۲)\n"
        f"🎯 **حد سود دوم (TP2):** {signal_data['tp2']} (ساختار بازار)\n"
        f"━━━━━━━━━━━━━━━\n"
        f"ℹ️ *نکته: پس از لمس TP1، حد ضرر را به نقطه ورود (ریکان یا ریسک‌فری) منتقل کنید.*\n"
        f"📉 شاخص روند (ADX): {signal_data['adx_value']}"
    )
    
    return send_telegram_message(message)
