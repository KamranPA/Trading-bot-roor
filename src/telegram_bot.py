# src/telegram_bot.py
import os
import sqlite3
import requests
from datetime import datetime

def send_telegram_message(text):
    """ارسال پیام با لایه توزیع‌شده ضد فیلتر و استفاده از گیت‌هاب سکرتز"""
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')
    
    if not token or not chat_id:
        print("❌ خطا: متغیرهای محیطی تلگرام تنظیم نشده‌اند.")
        return False

    token = str(token).strip()
    chat_id = str(chat_id).strip()

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
        f"📊 شاخص نوسان (ATR %): {signal_data['feat_atr_percent']}%\n"
        f"📈 قدرت روند واقعی (ADX): {signal_data['feat_adx']}\n"
        f"🔊 ضریب حجم معاملات: {signal_data['feat_vol_ratio']}x\n\n"
        f"✓ این موقعیت با لایه فیلترینگ هوش مصنوعی (ML) ارزیابی شده است."
    )
    return send_telegram_message(message)

def send_performance_report():
    """📊 استخراج آمار دیتابیس و ارسال گزارش جامع عملکرد ربات به تلگرام"""
    # لود آدرس دیتابیس بر اساس ساختار پروژه
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    db_path = os.path.join(base_dir, "data", "trading_bot.db")
    
    if not os.path.exists(db_path):
        print("⚠️ دیتابیس برای گزارش‌دهی یافت نشد.")
        return False
        
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # ۱. تعداد کل سیگنال‌ها
        cursor.execute("SELECT COUNT(*) FROM signals")
        total_signals = cursor.fetchone()[0]
        
        # ۲. تعداد پوزیشن‌های باز فعلی
        cursor.execute("SELECT COUNT(*) FROM signals WHERE status = 'OPEN'")
        open_count = cursor.fetchone()[0]
        
        # ۳. تعداد پوزیشن‌های بسته شده
        cursor.execute("SELECT COUNT(*) FROM signals WHERE status = 'CLOSED'")
        closed_count = cursor.fetchone()[0]
        
        # ۴. محاسبات سود و زیان (معاملات بسته شده)
        cursor.execute("SELECT COUNT(*) FROM signals WHERE status = 'CLOSED' AND pnl_percent > 0")
        wins = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM signals WHERE status = 'CLOSED' AND pnl_percent <= 0")
        losses = cursor.fetchone()[0]
        
        cursor.execute("SELECT SUM(pnl_percent) FROM signals WHERE status = 'CLOSED'")
        total_pnl = cursor.fetchone()[0] or 0.0
        
        # ۵. دریافت آخرین وضعیت لاگ‌های اسکن بازار
        cursor.execute("SELECT COUNT(*) FROM scan_logs WHERE result LIKE '%Blocked by AI%'")
        ai_blocked_count = cursor.fetchone()[0]
        
        conn.close()
        
        # محاسبه نرخ برد (Win Rate)
        win_rate = (wins / closed_count * 100) if closed_count > 0 else 0.0
        pnl_emoji = "📈" if total_pnl >= 0 else "📉"
        
        # قالب‌بندی پیام گزارش به زبان فارسی
        report_message = (
            f"📊 **گزارش عملکرد و کارنامه معاملاتی ربات**\n"
            f"📅 تاریخ گزارش: {datetime.utcnow().strftime('%Y-%m-%d')}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🤖 **آمار کل معاملات:**\n"
            f"🔹 کل سیگنال‌های صادر شده: {total_signals}\n"
            f"⏳ پوزیشن‌های باز در بازار: {open_count}\n"
            f"✅ پوزیشن‌های خاتمه یافته: {closed_count}\n\n"
            f"🧠 **عملکرد هوش مصنوعی و استراتژی:**\n"
            f"🟢 معاملات سودده (تارگت): {wins}\n"
            f"🔴 معاملات زیان‌ده (استاپ): {losses}\n"
            f"🎯 نرخ برد فیلترها (Win Rate): **{win_rate:.1f}%**\n"
            f"🛡️ موقعیت‌های مشکوک مسدود شده توسط AI: {ai_blocked_count}\n\n"
            f"{pnl_emoji} **بازدهی خالص سیستم:**\n"
            f"💰 مجموع سود/زیان خالص: **{total_pnl:.2f}%**\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"⚡ _گزارش خودکار از دیتابیس لایو گیت‌هاب اکشنز_"
        )
        
        return send_telegram_message(report_message)
        
    except Exception as e:
        print(f"❌ خطا در تولید گزارش تلگرام: {e}")
        return False
