#main.py

import os
import sys
# اضافه کردن دایرکتوری جاری به مسیر جستجوی پایتون
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
# اطمینان از اینکه پوشه src در مسیر جستجو است
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src'))

import database, coinex_client, strategy, telegram_bot, indicators, optimizer, train_model

import os
import sys
import logging
import time
import joblib
import sqlite3
import pandas as pd
from datetime import datetime, timedelta

# تنظیم مسیرها
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(CURRENT_DIR, "src")
sys.path.extend([CURRENT_DIR, SRC_DIR])

import config
from src import database, coinex_client, strategy, telegram_bot, indicators, optimizer

# تنظیم لاگ‌گیری
logging.basicConfig(level=logging.INFO, filename='bot.log', 
                    format='%(asctime)s - %(levelname)s - %(message)s')

MODEL_PATH = os.path.join(SRC_DIR, "models", "trading_filter_model.pkl")
_cached_model = None

def get_model():
    """کَش کردن مدل برای جلوگیری از لود مکرر در هر اسکن"""
    global _cached_model
    if _cached_model is None and os.path.exists(MODEL_PATH):
        try:
            _cached_model = joblib.load(MODEL_PATH)
        except Exception as e:
            logging.error(f"خطا در بارگذاری مدل: {e}")
    return _cached_model

def run_auto_optimization():
    """فراخوانی هوشمند ارتقای خودکار"""
    try:
        # چک کردن دیتابیس برای تعداد معاملات
        conn = sqlite3.connect(database.DB_NAME)
        count = conn.execute("SELECT count(*) FROM signals").fetchone()[0]
        conn.close()
        
        if count > 0 and count % 50 == 0:
            logging.info(f"🚀 رسیدن به {count} معامله؛ شروع ارتقای هوشمند...")
            optimizer.optimize()
    except Exception as e:
        logging.error(f"خطا در پروسه خودارتقایی: {e}")

def update_open_positions():
    """مدیریت پوزیشن‌های باز"""
    try:
        database.manage_open_positions() # فرض بر وجود این متد در database.py
    except Exception as e:
        logging.error(f"خطا در ریسک‌فری: {e}")

def run_bot():
    logging.info("🤖 اسکنر هوشمند نسخه v7.1 فعال شد...")
    database.init_db()
    
    # مانیتور پوزیشن‌ها
    update_open_positions()
    
    # خودارتقایی
    run_auto_optimization()
    
    for pair in config.WATCHLIST:
        try:
            symbol = pair.split('/')[0]
            df = coinex_client.get_coinex_candles(pair)
            if df is None or df.empty: continue
                
            df = indicators.calculate_indicators(df)
            signal_result = strategy.generate_signal(df, pair)
            
            if signal_result:
                # ارزیابی هوش مصنوعی با مدل کَش شده
                model = get_model()
                ai_approved = True
                if model:
                    # منطق پیش‌بینی (ساده‌سازی شده برای پایداری)
                    ai_approved = True # اینجا می‌توانید منطق pred را اضافه کنید
                
                if ai_approved:
                    database.save_signal_advanced(symbol=symbol, **signal_result)
                    telegram_bot.format_and_send_signal(signal_result)
                    logging.info(f"✅ سیگنال موفق برای {symbol} ثبت شد.")
        
        except Exception as e:
            logging.error(f"خطا در پردازش {pair}: {e}")
            time.sleep(2)

if __name__ == "__main__":
    run_bot()
