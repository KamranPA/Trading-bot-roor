# ---------------------------------------------------------
# FILE PATH: /src/telegram_bot.py
# ---------------------------------------------------------
import requests
import config
import os
import sqlite3

def send_telegram_message(text):
    """ارسال پیام به تلگرام با فرمت ایمن HTML برای جلوگیری از خطای پارس کاراکترها"""
    token = os.environ.get("TELEGRAM_BOT_TOKEN") or getattr(config, 'TELEGRAM_BOT_TOKEN', None)
    chat_id = os.environ.get("TELEGRAM_CHAT_ID") or getattr(config, 'TELEGRAM_CHAT_ID', None)
    
    if not token or not chat_id:
        print("⚠️ توکن تلگرام یا چت‌آیدی یافت نشد.")
        return
        
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    # تغییر پارس مود به HTML جهت پایداری ۱۰۰٪ در ارسال علائم ریاضی و خط تیره‌ها
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code != 200:
            print(f"❌ خطای سرور تلگرام: {response.text}")
    except Exception as e:
        print(f"❌ خطای شبکه تلگرام: {e}")

def format_and_send_signal(signal_data):
    """💎 نمایش ۱۰‌بعدی سیگنال: بهینه‌شده با ساختار HTML ایمن"""
    d = signal_data
    
    vol_status = "✅ تایید شد" if float(d.get('feat_vol_confirm', 0)) == 1.0 else "⚠️ ضعیف"
    icon = "🟢 #LONG" if d['direction'] == "LONG" else "🔴 #SHORT"
    
    # استانداردسازی نام جفت‌ارز
    clean_pair = str(d['pair']).replace('_', '/')
    
    message = (
        f"<b>{icon} سیگنال مدیریت‌شده ۱۰‌بعدی</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"🪙 <b>جفت ارز:</b> <code>{clean_pair}</code>\n"
        f"🔮 <b>جهت:</b> <code>{d['direction']}</code>\n\n"
        f"💵 <b>ورود:</b> <code>{d['entry_price']}</code>\n"
        f"🛡️ <b>استاپ:</b> <code>{d['stop_loss']}</code>\n"
        f"🎯 <b>تارگت ۱:</b> <code>{d['tp1']}</code> | 🎯 <b>تارگت ۲:</b> <code>{d['tp2']}</code>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"💰 <b>حجم ورود:</b> <code>{d['position_size']} USDT</code>\n"
        f"📊 <b>تاییدیه حجم (Vol Conf):</b> {vol_status}\n"
        f"📈 <b>قدرت روند (ADX):</b> <code>{round(d.get('feat_adx', 0), 1)}</code>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"📡 <i>نسخه سیستم: v7.1</i>"
    )
    
    send_telegram_message(message)

def send_performance_report():
    """📊 استخراج عملکرد معاملات از دیتابیس و ارسال کارنامه ماهانه به تلگرام"""
    try:
        from src import database
        db_path = getattr(database, 'DB_NAME', 'data/trading_bot.db')
    except ImportError:
        db_path = 'data/trading_bot.db'
    
    # اگر پوشه data/ نباشد، مسیر ریشه را هم چک می‌کند (برای پایداری بکتست)
    if not os.path.exists(db_path) and os.path.exists('trading_bot.db'):
        db_path = 'trading_bot.db'
        
    if not os.path.exists(db_path):
        print(f"⚠️ فایل دیتابیس در مسیر [{db_path}] یافت نشد.")
        return

    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            # ۱. بررسی هوشمند وجود جدول signals
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='signals'")
            if not cursor.fetchone():
                print("⚠️ جدول signals هنوز در دیتابیس ساخته نشده است.")
                return
                
            # ۲. محاسبه آمار کل معاملات بسته شده
            cursor.execute("SELECT COUNT(*), SUM(pnl_percent) FROM signals WHERE status = 'CLOSED'")
            total_trades, total_pnl = cursor.fetchone()
            
            # ۳. محاسبه پوزیشن‌های برنده
            cursor.execute("SELECT COUNT(*) FROM signals WHERE status = 'CLOSED' AND pnl_percent > 0")
            wins = cursor.fetchone()[0]
            
        if not total_trades or total_trades == 0:
            message = (
                "📊 <b>گزارش عملکرد ماهانه هوش مصنوعی</b>\n"
                "━━━━━━━━━━━━━━━\n"
                "ℹ️ در این ماه هیچ معاملاتی در دیتابیس ثبت یا بسته نشده است."
            )
            send_telegram_message(message)
            return

        total_pnl = total_pnl if total_pnl is not None else 0.0
        win_rate = (wins / total_trades) * 100 if total_trades > 0 else 0
        status_icon = "🟢" if total_pnl >= 0 else "🔴"
        
        message = (
            f"📊 <b>کارنامه عملکرد ماهانه ربات (v7.1)</b>\n"
            f"━━━━━━━━━━━━━━━\n"
            f"📦 <b>کل معاملات ثبت شده:</b> <code>{total_trades}</code>\n"
            f"🎯 <b>تعداد بردهـا:</b> <code>{wins}</code> معامله\n"
            f"📈 <b>نرخ برد (Win Rate):</b> <code>{win_rate:.1f}%</code>\n"
            f"━━━━━━━━━━━━━━━\n"
            f"{status_icon} <b>کل بازدهی خالص دیتابیس:</b> <code>{total_pnl:.2f}%</code>\n"
            f"━━━━━━━━━━━━━━━\n"
            f"🧠 <i>موتور هوش مصنوعی با موفقیت با این دیتا بازآموزی و بهینه‌سازی شد.</i>"
        )
        send_telegram_message(message)
        print("✅ گزارش عملکرد با موفقیت به تلگرام ارسال شد.")
        
    except Exception as e:
        print(f"❌ خطا در تولید گزارش عملکرد تلگرام: {e}")
