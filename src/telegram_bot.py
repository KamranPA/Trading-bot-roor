# ---------------------------------------------------------
# FILE PATH: /src/telegram_bot.py
# ---------------------------------------------------------
import requests
import config
import os
import sqlite3

def send_telegram_message(text):
    # استفاده از مقادیر ایمن از محیط (Env) یا فایل کانفیگ
    token = os.environ.get("TELEGRAM_BOT_TOKEN") or getattr(config, 'TELEGRAM_BOT_TOKEN', None)
    chat_id = os.environ.get("TELEGRAM_CHAT_ID") or getattr(config, 'TELEGRAM_CHAT_ID', None)
    
    if not token or not chat_id:
        print("⚠️ توکن تلگرام یا چت‌آیدی یافت نشد.")
        return
        
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code != 200:
            print(f"❌ خطای سرور تلگرام: {response.text}")
    except Exception as e:
        print(f"❌ خطای شبکه تلگرام: {e}")

def format_and_send_signal(signal_data):
    """💎 نمایش ۱۰‌بعدی سیگنال: اضافه شدنِ نمایشِ تاییدیه حجم (Volume Confirmation)"""
    d = signal_data
    
    # 🧠 تعیین وضعیت تاییدیه حجم برای نمایش بصری
    vol_status = "✅ تایید شد" if float(d.get('feat_vol_confirm', 0)) == 1.0 else "⚠️ ضعیف"
    icon = "🟢 #LONG" if d['direction'] == "LONG" else "🔴 #SHORT"
    
    # پاکسازی نام جفت ارز برای جلوگیری از خطای تلگرام در مورد کاراکتر اسلش
    clean_pair = str(d['pair']).replace('_', '/')
    
    message = (
        f"{icon} **سیگنال مدیریت‌شده ۱۰‌بعدی**\n"
        f"━━━━━━━━━━━━━━━\n"
        f"🪙 **جفت ارز:** `{clean_pair}`\n"
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

def send_performance_report():
    """📊 استخراج عملکرد معاملات از دیتابیس و ارسال کارنامه ماهانه به تلگرام"""
    from src import database # لود داینامیک دیتابیس پروژه جهت جلوگیری از خطای Circular Import
    
    db_path = getattr(database, 'DB_NAME', 'data/trading_bot.db')
    
    if not os.path.exists(db_path):
        print(f"⚠️ فایل دیتابیس در مسیر [{db_path}] یافت نشد.")
        return

    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            # ۱. بررسی وجود جدول signals برای جلوگیری از کرش ربات
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='signals'")
            if not cursor.fetchone():
                print("⚠️ جدول signals هنوز در دیتابیس ساخته نشده است.")
                return
                
            # ۲. محاسبه آمار کل پوزیشن‌های بسته شده در بکتست یا بازار زنده
            cursor.execute("SELECT COUNT(*), SUM(pnl_percent) FROM signals WHERE status = 'CLOSED'")
            total_trades, total_pnl = cursor.fetchone()
            
            # ۳. محاسبه پوزیشن‌های برنده (سود بالای صفر درصد یا ریسک‌فری‌های مثبت)
            cursor.execute("SELECT COUNT(*) FROM signals WHERE status = 'CLOSED' AND pnl_percent > 0")
            wins = cursor.fetchone()[0]
            
        if not total_trades or total_trades == 0:
            message = (
                "📊 **گزارش عملکرد ماهانه هوش مصنوعی**\n"
                "━━━━━━━━━━━━━━━\n"
                "ℹ️ در این ماه هیچ معاملاتی در دیتابیس ثبت یا بسته نشده است."
            )
            send_telegram_message(message)
            return

        total_pnl = total_pnl if total_pnl is not None else 0.0
        win_rate = (wins / total_trades) * 100 if total_trades > 0 else 0
        status_icon = "🟢" if total_pnl >= 0 else "🔴"
        
        message = (
            f"📊 **کارنامه عملکرد ماهانه ربات (v7.1)**\n"
            f"━━━━━━━━━━━━━━━\n"
            f"📦 **کل معاملات بسته شده:** `{total_trades}`\n"
            f"🎯 **تعداد بردهـا:** `{wins}` معامله\n"
            f"📈 **نرخ برد (Win Rate):** `{win_rate:.1f}%`\n"
            f"━━━━━━━━━━━━━━━\n"
            f"{status_icon} **کل بازدهی خالص معاملات:** `{total_pnl:.2f}%`\n"
            f"━━━━━━━━━━━━━━━\n"
            f"🧠 *موتور هوش مصنوعی بر اساس این دیتا بازآموزی و بهینه‌سازی شد.*"
        )
        send_telegram_message(message)
        print("✅ گزارش عملکرد با موفقیت به تلگرام ارسال شد.")
        
    except Exception as e:
        print(f"❌ خطا در تولید گزارش عملکرد تلگرام: {e}")
