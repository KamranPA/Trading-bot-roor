# main.py
# فایل اصلی اجرای ربات (نسخه v3.1 - اصلاح‌شده با فیلتر UTC و لیست واچ‌لیست پویا)

import os
import sys
import pandas as pd
import sqlite3
from datetime import datetime

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.append(CURRENT_DIR)

SRC_DIR = os.path.join(CURRENT_DIR, "src")
if SRC_DIR not in sys.path:
    sys.path.append(SRC_DIR)

import config
import database
from src import coinex_client
from src import strategy
from src import telegram_bot
from src import indicators

def is_telegram_locked_8h(symbol, hours_limit=8):
    """بررسی هوشمند ریاضی اختلاف زمان آخرین پوزیشن بر پایه UTC جهت فعال‌سازی فیلتر ۸ ساعته"""
    db_path = database.DB_NAME
    if not os.path.exists(db_path):
        return False
        
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        query = "SELECT timestamp FROM signals WHERE symbol = ? ORDER BY id DESC LIMIT 1"
        cursor.execute(query, (symbol,))
        result = cursor.fetchone()
        conn.close()
        
        if result and result[0]:
            clean_time_str = str(result[0]).replace('T', ' ').split('.')[0]
            try:
                last_signal_time = datetime.strptime(clean_time_str, '%Y-%m-%d %H:%M:%S')
            except Exception:
                return False
                
            # محاسبه اختلاف بر پایه زمان استاندارد بین‌المللی گیت‌هاب (UTC)
            time_difference = datetime.utcnow() - last_signal_time
            hours_passed = abs(time_difference.total_seconds() / 3600)
            
            print(f"⏱️ [Filter Check] برای {symbol}: {hours_passed:.2f} ساعت از آخرین پوزیشن گذشته است.")
            
            if hours_passed < hours_limit or hours_passed > (24 - hours_limit):
                print(f"🔒 [Locked] ارسال سیگنال تکراری {symbol} به تلگرام مسدود شد.")
                return True
                
        return False
    except Exception as e:
        print(f"⚠️ خطا در بررسی فیلتر زمانی تلگرام: {e}")
        return False

def run_bot():
    print("🤖 اسکنر هوشمند نسخه v3.1 (معماری داده تفکیکی و ضد اسپم UTC) فعال شد...")
    database.init_db()
    database.check_filters_lock()
    
    bot_mode = database.get_setting("bot_status", "ACTIVE")
    if bot_mode != "ACTIVE":
        print("🛑 ربات از طریق تنظیمات دیتابیس غیرفعال شده است.")
        return
    
    # 🛠️ اصلاح حیاتی: استفاده مستقیم از واچ‌لیست مرکزی بجای لیست دستی قدیمی
    for pair in config.WATCHLIST:
        symbol = pair.split('/')[0] # استخراج نام ارز (مثلاً BTC) برای دیتابیس
        print(f"\n🔄 اسکنر در حال پردازش و محاسبات تکنیکال: {pair}...")
        
        df = coinex_client.get_coinex_candles(pair)
        if df is None or df.empty:
            print(f"❌ دیتایی برای جفت‌ارز {pair} دریافت نشد.")
            continue
            
        df = indicators.calculate_indicators(df)
        signal_result = strategy.generate_signal(df, pair)
        
        if signal_result and isinstance(signal_result, dict):
            direction = signal_result['direction']
            print(f"🎯 استراتژی روی {symbol} سیگنال {direction} صادر کرد.")
            
            # ثبت در لاگ اسکن
            database.log_scan(symbol, f"Signal {direction} | Entry: {signal_result['entry_price']}")
            
            # فیلتر نشت لایو ۸ ساعته (اکنون با UTC کالیبره شده است)
            if is_telegram_locked_8h(symbol, hours_limit=8):
                print(f"⏭️ ارسال به تلگرام مسدود شد: فیلتر ۸ ساعته برای {symbol} فعال است.")
                continue
                
            # ذخیره‌سازی داده‌ها در معماری تفکیکی دیتابیس
            database.save_signal_advanced(
                symbol=symbol,
                direction=direction,
                entry_price=signal_result['entry_price'],
                stop_loss=signal_result['stop_loss'],
                tp1=signal_result['tp1'],
                tp2=signal_result['tp2'],
                status="OPEN"
            )
            
            telegram_bot.format_and_send_signal(signal_result)
            
        else:
            print(f"🔍 ارز {symbol} شرایط ورود به معامله را نداشت.")
            database.log_scan(symbol, "No Signal")
            
    print("\n🏁 فرآیند دوره جاری اسکن بازار به پایان رسید.")

if __name__ == "__main__":
    run_bot()
