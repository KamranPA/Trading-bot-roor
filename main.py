# main.py
# فایل اصلی اجرای ربات (نسخه v2.0 - هماهنگ شده با دیتابیس جامع و فیلتر ریاضی ۸ ساعته)

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
from src import indicators

SYMBOLS = ["BTC", "ETH", "SOL"]

def is_telegram_locked_8h(symbol, hours_limit=8):
    """
    بررسی هوشمند جدول signals برای چک کردن قفل ۸ ساعته تلگرام.
    تفاضل زمانی را به صورت ریاضی محاسبه می‌کند تا با تفاوت ساعت سرور و فرمت‌ها تداخل نداشته باشد.
    """
    # استفاده از مسیر استاندارد و یکپارچه شده با ماژول database
    db_path = database.DB_NAME
    if not os.path.exists(db_path):
        return False
        
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # استخراج آخرین سیگنال ثبت شده برای ارز
        query = """
            SELECT timestamp FROM signals 
            WHERE symbol = ? 
            ORDER BY id DESC LIMIT 1
        """
        cursor.execute(query, (symbol,))
        result = cursor.fetchone()
        conn.close()
        
        if result and result[0]:
            last_signal_time_str = str(result[0])
            
            # پاک‌سازی و استخراج بخش تاریخ و ساعت اصلی
            clean_time_str = last_signal_time_str.replace('T', ' ').split('.')[0]
            
            try:
                last_signal_time = datetime.strptime(clean_time_str, '%Y-%m-%d %H:%M:%S')
            except Exception:
                print(f"⚠️ [Filter] نتوانست فرمت زمان دیتابیس ({last_signal_time_str}) را بخواند.")
                return False
                
            # محاسبه اختلاف ساعت واقعی به صورت عددی
            time_difference = datetime.now() - last_signal_time
            hours_passed = abs(time_difference.total_seconds() / 3600)
            
            print(f"⏱️ [Filter Check] برای {symbol}: {hours_passed:.2f} ساعت از آخرین سیگنال گذشته است.")
            
            # اگر اختلاف زمان کمتر از ۸ ساعت باشد یا به خاطر تفاوت ریجن ساعت‌ها نزدیک به هم باشند، قفل فعال است
            if hours_passed < hours_limit or hours_passed > (24 - hours_limit):
                print(f"🔒 [Locked] ارسال سیگنال تکراری {symbol} به تلگرام مسدود شد.")
                return True
                
        return False
    except Exception as e:
        print(f"⚠️ خطا در بررسی فیلتر زمانی تلگرام: {e}")
        return False

def run_bot():
    print("🤖 اسکنر هوشمند نسخه v2.0 (مجهز به فیلتر ضد نشت لایو و دیتابیس غنی) فعال شد...")
    database.init_db()
    database.check_filters_lock()
    
    for symbol in SYMBOLS:
        pair = f"{symbol}/USDT"
        print(f"\n🔄 اسکنر در حال پردازش و محاسبات تکنیکال: {pair}...")
        
        # ۱. واکشی داده‌ها و محاسبه اندیکاتورها
        df = coinex_client.get_coinex_candles(pair)
        
        if df is None or df.empty:
            print(f"❌ دیتایی برای جفت‌ارز {pair} دریافت نشد.")
            continue
            
        df = indicators.calculate_indicators(df)
        
        # ۲. سنجش وضعیت استراتژی روی کندل لایو
        signal_result = strategy.generate_signal(df, pair)
        
        if signal_result and isinstance(signal_result, dict):
            direction = signal_result['direction']
            print(f"🎯 استراتژی روی {symbol} سیگنال {direction} صادر کرد.")
            
            # ۳. ثبت دیتای واقعی استراتژی در اسکن لاگ (برای تغذیه هوش مصنوعی)
            database.log_scan(symbol, f"Signal {direction} | Entry: {signal_result['entry_price']}")
            
            # ۴. بررسی قفل ۸ ساعته تلگرام درست قبل از ارسال نهایی
            if is_telegram_locked_8h(symbol, hours_limit=8):
                print(f"⏭️ ارسال به تلگرام مسدود شد: فیلتر ۸ ساعته برای {symbol} فعال است.")
                continue
                
            # ۵. 🔥 ذخیره در دیتابیس با فرمت نسخه v2.0 (ارسال تمام تارگت‌ها و حد ضرر جهت جلوگیری از ارور تعداد آرگومان)
            database.save_signal(
                symbol=symbol,
                direction=direction,
                entry_price=signal_result['entry_price'],
                tp1=signal_result['tp1'],
                tp2=signal_result['tp2'],
                stop_loss=signal_result['stop_loss'],
                status="OPEN"
            )
            
            # ۶. ارسال به تلگرام
            telegram_bot.format_and_send_signal(signal_result)
            
        else:
            print(f"🔍 ارز {symbol} شرایط ورود به معامله را نداشت.")
            database.log_scan(symbol, "No Signal")
            
    print("\n🏁 فرآیند دوره جاری اسکن بازار به پایان رسید.")

if __name__ == "__main__":
    run_bot()
