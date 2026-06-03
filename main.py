# main.py
import os
import sys
import pandas as pd
import sqlite3
from datetime import datetime, timedelta

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

SYMBOLS = ["BTC", "ETH", "SOL"]

def is_telegram_locked_8h(symbol, hours_limit=8):
    """
    بررسی دقیق و ضد نشت جدول signals برای چک کردن قفل ۸ ساعته ارسال به تلگرام.
    بدون وابستگی به فرمت دقیق کوئری دیتابیس، تفاضل زمانی را به صورت عددی محاسبه می‌کند.
    """
    db_path = os.path.join(CURRENT_DIR, "data", "trading_bot.db")
    if not os.path.exists(db_path):
        return False
        
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # واکشی آخرین سیگنال صادر شده برای ارز بدون محدود کردن کوئری با زمان سرور
        query = """
            SELECT timestamp FROM signals 
            WHERE symbol = ? 
            ORDER BY id DESC LIMIT 1
        """
        cursor.execute(query, (symbol,))
        result = cursor.fetchone()
        conn.close()
        
        if result and result[0]:
            last_signal_time_str = result[0]
            
            # تبدیل منعطف رشته به آبجکت datetime (پشتیبانی از فرمت‌های با یا بدون میلی‌ثانیه)
            try:
                last_signal_time = datetime.strptime(last_signal_time_str, '%Y-%m-%d %H:%M:%S')
            except ValueError:
                # هندل کردن فرمت‌های حاوی میلی‌ثانیه یا ساختار استاندارد ISO
                last_signal_time = datetime.fromisoformat(last_signal_time_str.split('.')[0])
                
            # محاسبه تفاضل واقعی بر اساس ساعت عددی
            time_difference = datetime.now() - last_signal_time
            hours_passed = time_difference.total_seconds() / 3600
            
            print(f"⏱️ [بررسی فیلتر] برای {symbol}: {hours_passed:.2f} ساعت از آخرین سیگنال گذشته است.")
            
            if hours_passed < hours_limit:
                return True  # قفل فعال است، اجازه ارسال نده
                
        return False  # قفل باز است، سیگنال جدید مجاز است
    except Exception as e:
        print(f"⚠️ خطا در بررسی فیلتر زمانی تلگرام: {e}")
        return False

def run_bot():
    print("🤖 اسکنر هوشمند نسخه v1.7 (مجهز به لایه‌بندی لاگ پیشرفته) فعال شد...")
    database.init_db()
    database.check_filters_lock()
    
    for symbol in SYMBOLS:
        pair = f"{symbol}/USDT"
        print(f"\n🔄 اسکنر در حال پردازش و محاسبات تکنیکال: {pair}...")
        
        # ۱. واکشی داده‌ها و محاسبه اندیکاتورها در هر شرایطی انجام می‌شود
        df = coinex_client.get_coinex_candles(pair)
        
        if df is None or df.empty:
            print(f"❌ دیتایی برای جفت‌ارز {pair} دریافت نشد.")
            continue
            
        from src import indicators
        df = indicators.calculate_indicators(df)
        
        # ۲. سنجش وضعیت استراتژی روی کندل لایو
        signal_result = strategy.generate_signal(df, pair)
        
        if signal_result and isinstance(signal_result, dict):
            direction = signal_result['direction']
            print(f"🎯 استراتژی روی {symbol} سیگنال {direction} صادر کرد.")
            
            # ۳. ثبت دیتای واقعی استراتژی در اسکن لاگ (برای تغذیه هوش مصنوعی ماهانه)
            database.log_scan(symbol, f"Signal {direction} | Entry: {signal_result['entry_price']}")
            
            # ۴. بررسی قفل ۸ ساعته تلگرام درست قبل از ارسال نهایی
            if is_telegram_locked_8h(symbol, hours_limit=8):
                print(f"⏭️ ارسال به تلگرام مسدود شد: کمتر از ۸ ساعت از آخرین سیگنال ارسال‌شده {symbol} گذشته است.")
                continue
                
            # ۵. ذخیره در جدول پوزیشن‌های اصلی و ارسال به تلگرام (در صورت عبور از فیلتر ۸ ساعته)
            database.save_signal(symbol, direction, signal_result['entry_price'], status="OPEN")
            telegram_bot.format_and_send_signal(signal_result)
            
        else:
            print(f"🔍 ارز {symbol} شرایط ورود به معامله را نداشت.")
            # ثبت لاگ عدم صدور سیگنال برای محاسبات آماری دیتابیس
            database.log_scan(symbol, "No Signal")
            
    print("\n🏁 فرآیند دوره جاری اسکن بازار به پایان رسید.")

if __name__ == "__main__":
    run_bot()
