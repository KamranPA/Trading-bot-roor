# src/telegram_bot.py
# نسخه نهایی v7.3 - مجهز به لایه گزارش فرصت‌های نادیده گرفته شده

import requests
import config
import os

def send_telegram_message(text):
    """ارسال پیام متنی ساده به تلگرام"""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", config.TELEGRAM_BOT_TOKEN)
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", config.TELEGRAM_CHAT_ID)
    
    if not token or not chat_id:
        print("⚠️ توکن تلگرام یا چت‌آیدی تنظیم نشده است.")
        return
        
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code != 200:
            print(f"❌ خطا در ارسال تلگرام: {response.text}")
    except Exception as e:
        print(f"❌ خطای ارتباطی تلگرام: {e}")

def format_and_send_signal(signal_data):
    """💎 قالب‌بندی و ارسال سیگنال لایو"""
    icon = "🟢 #LONG" if signal_data['direction'] == "LONG" else "🔴 #SHORT"
    target_icon = "🏹" if signal_data['direction'] == "LONG" else "🎯"
    
    message = (
        f"{icon} **سیگنال جدید دستیار هوشمند ۳۶۰ درجه**\n"
        f"━━━━━━━━━━━━━━━\n"
        f"🪙 **جفت ارز:** `{signal_data['pair']}`\n"
        f"🔮 **جهت ورود:** {signal_data['direction']}\n\n"
        f"💵 **نقطه ورود (Entry):** `{signal_data['entry_price']}`\n"
        f"🛡️ **حد ضرر (Stop Loss):** `{signal_data['stop_loss']}` (Risk: {signal_data.get('sl_percent', 0)}%)\n\n"
        f"{target_icon} **تارگت اول (TP1):** `{signal_data['tp1']}`\n"
        f"{target_icon} **تارگت دوم (TP2):** `{signal_data['tp2']}`\n"
        f"━━━━━━━━━━━━━━━\n"
        f"💰 **لایه مدیریت سرمایه:**\n"
        f"📊 **حجم ورود:** `{signal_data.get('position_size', 0)} USDT`\n"
        f"━━━━━━━━━━━━━━━\n"
        f"📡 تایم‌فریم: {config.TIMEFRAME} | v7.3"
    )
    send_telegram_message(message)

def send_skipped_signal_message(signal_data, open_count):
    """⚠️ گزارش فرصت‌های نادیده گرفته شده (ظرفیت پر)"""
    msg = (
        f"⚠️ **گزارش فرصت نادیده گرفته شده (ظرفیت پر)**\n"
        f"━━━━━━━━━━━━━━━\n"
        f"🪙 **جفت ارز:** `{signal_data['pair']}` | **جهت:** `{signal_data['direction']}`\n"
        f"📊 **پوزیشن باز:** `{open_count} / {config.MAX_OPEN_POSITIONS}`\n\n"
        f"💵 **نقطه ورود:** `{signal_data['entry_price']}`\n"
        f"🛡️ **حد ضرر:** `{signal_data['stop_loss']}`\n"
        f"🏹 **تارگت اول:** `{signal_data['tp1']}`\n"
        f"🏹 **تارگت دوم:** `{signal_data['tp2']}`\n"
        f"━━━━━━━━━━━━━━━\n"
        f"💡 **وضعیت:** `تایید شده توسط AI`\n"
        f"*این سیگنال باز نشد، جهت آنالیز در دیتابیس ثبت گردید.*"
    )
    send_telegram_message(msg)
