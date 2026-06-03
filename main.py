# main.py - نسخه عیب‌یابی پیشرفته v1.8
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
    # اصلاح مسیر دیتابیس دقیقاً بر اساس ساختار database.py
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(BASE_DIR, "data", "trading_bot.db")
    
    print(f"🔍 [Debug] در حال بررسی قفل ۸ ساعته در مسیر: {db_path}")
    if not os.path.exists(db_path):
        print("⚠️ [Debug] فایل دیتابیس در این مسیر هنوز وجود ندارد.")
        return False
        
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        time_threshold = (datetime.now() - timedelta(hours=hours_limit)).strftime('%Y-%m-%d %H:%M:%S')
        
        query = """
            SELECT timestamp FROM signals 
            WHERE symbol = ? AND timestamp >= ? 
            ORDER BY id DESC LIMIT 1
        """
        cursor.execute(query, (symbol, time_threshold))
        result = cursor.fetchone()
        conn.close()
        print(f"📊 [Debug] نتیجه بررسی قفل برای {symbol}: {result is not None}")
        return result is not None  
    except Exception as e:
        print(f"❌ [Debug] خطا در دیتابیس فیلتر زمانی: {e}")
        return False

def run_bot():
    print(f"🤖 [Start] شروع اجرای ربات در زمان: {datetime.now()}")
    
    try:
        print("⚙️ [Step 1] مقداردهی اولیه دیتابیس...")
        database.init_db()
        database.check_filters_lock()
    except Exception as e:
        print(f"❌ [Error] خطا در راه‌اندازی اولیه دیتابیس: {e}")
        return

    for symbol in SYMBOLS:
        pair = f"{symbol}/USDT"
        print(f"\n━━━━━━━━━━━━━ {symbol} ━━━━━━━━━━━━━")
        
        try:
            print(f"📡 [Step 2] درخواست دیتا از صرافی برای {pair}...")
            df = coinex_client.get_coinex_candles(pair)
            
            if df is None or df.empty:
                print(f"❌ [Warning] دیتای زنده برای {pair} خالی است.")
                continue
                
            print(f"📊 [Step 3] محاسبه اندیکاتورها برای {symbol} (تعداد کندل: {len(df)})...")
            from src import indicators
            df = indicators.calculate_indicators(df)
            
            print(f"🎯 [Step 4] بررسی استراتژی و شکست سطوح برای {symbol}...")
            signal_result = strategy.generate_signal(df, pair)
            
            if signal_result and isinstance(signal_result, dict):
                direction = signal_result['direction']
                print(f"✅ [Signal] استراتژی سیگنال {direction} داد. قیمت ورود: {signal_result['entry_price']}")
                
                print(f"📝 [Step 5] ثبت لاگ سیگنال در scan_logs...")
                database.log_scan(symbol, f"Signal {direction} | Entry: {signal_result['entry_price']}")
                
                if is_telegram_locked_8h(symbol, hours_limit=8):
                    print(f"⏭️ [Filter] تلگرام قفل است. ارسال پیام برای {symbol} انجام نمی‌شود.")
                    continue
                    
                print(f"💾 [Step 6] ذخیره در جدول اصلی signals...")
                database.save_signal(symbol, direction, signal_result['entry_price'], status="OPEN")
                
                print(f"🚀 [Step 7] ارسال نهایی به تلگرام...")
                telegram_bot.format_and_send_signal(signal_result)
            else:
                print(f"🔍 [No Signal] شرایط استراتژی برای {symbol} برقرار نبود.")
                database.log_scan(symbol, "No Signal")
                
        except Exception as item_error:
            print(f"❌ [Loop Error] خطای غیرمنتظره در پردازش ارز {symbol}: {item_error}")
            
    print(f"\n🏁 [End] پایان اجرای ربات در زمان: {datetime.now()}")

if __name__ == "__main__":
    run_bot()
