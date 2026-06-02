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

def is_signal_duplicate_dynamic(symbol, hours_limit=8):
    """بررسی دقیق جهت عدم انتشار سیگنال تکراری در بازه قفل"""
    db_path = os.path.join(CURRENT_DIR, "data", "trading_bot.db")
    if not os.path.exists(db_path):
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
        return result is not None  
    except Exception as e:
        print(f"⚠️ خطا در بررسی فیلتر داینامیک: {e}")
        return False

def run_bot():
    print("🤖 اسکنر هوشمند نسخه v1.6 فعال شد...")
    database.init_db()
    database.check_filters_lock()
    
    for symbol in SYMBOLS:
        pair = f"{symbol}/USDT"
        print(f"\n🔄 اسکنر در حال واکشی داده‌های: {pair}...")
        
        if is_signal_duplicate_dynamic(symbol, hours_limit=8):
            print(f"⏭️ فیلتر زمان‌محور فعال: ارز {symbol} در وضعیت قفل ۸ ساعته قرار دارد.")
            database.log_scan(symbol, "Skipped | Locked by 8h Filter")
            continue
            
        # واکشی استاندارد داده‌ها از کلاینت رسمی CCXT پیاده‌سازی شده در پروژه
        df = coinex_client.get_coinex_candles(pair)
        
        if df is None or df.empty:
            print(f"❌ دیتایی برای جفت‌ارز {pair} دریافت نشد.")
            continue
            
        # تزریق اندیکاتورها از ماژول اختصاصی شما
        from src import indicators
        df = indicators.calculate_indicators(df)
        
        signal_result = strategy.generate_signal(df, pair)
        
        if signal_result and isinstance(signal_result, dict):
            print(f"✅ سیگنال تایید شده {signal_result['direction']} تولید شد.")
            
            # ثبت آنی در دیتابیس محلی پیش از ارسال به تلگرام برای جلوگیری از Race Condition
            database.save_signal(symbol, signal_result['direction'], signal_result['entry_price'], status="OPEN")
            database.log_scan(symbol, f"Signal {signal_result['direction']} | Entry: {signal_result['entry_price']}")
            
            # ارسال نهایی پیام ساختاریافته به کانال یا ربات تلگرام
            telegram_bot.format_and_send_signal(signal_result)
        else:
            print(f"🔍 ارز {symbol} شرایط ورود به معامله را ندارد.")
            database.log_scan(symbol, "No Signal")
            
    print("\n🏁 فرآیند دوره جاری اسکن بازار به پایان رسید.")

if __name__ == "__main__":
    run_bot()
