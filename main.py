# ---------------------------------------------------------
# FILE PATH: /main.py
# ---------------------------------------------------------

import os
import sys
import logging
import time
import joblib
import sqlite3

# ۱. تنظیم هوشمند مسیرها (بدون وابستگی به محل اجرا)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(BASE_DIR, 'src')

# افزودن مسیرها به ابتدای لیست جستجوی پایتون (اولویت بالا)
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

# ۲. واردات ماژول‌ها - استفاده از Try/Except برای دیباگ سریع‌تر
try:
    import config
    from src import database, coinex_client, strategy, telegram_bot, indicators, optimizer
except ImportError as e:
    logging.critical(f"خطای بحرانی در وارد کردن ماژول‌ها: {e}")
    sys.exit(1)

# ۳. تنظیم لاگ‌گیری استاندارد (ذخیره در فایل برای بررسی در گیت‌هاب)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()] # لاگ‌ها در گیت‌هاب اکشن مستقیم چاپ می‌شوند
)

MODEL_PATH = os.path.join(SRC_DIR, "models", "trading_filter_model.pkl")

def get_model():
    """لود مدل با بررسی وجود فایل و مدیریت حافظه"""
    if not os.path.exists(MODEL_PATH):
        logging.warning("فایل مدل یافت نشد. بدون هوش مصنوعی ادامه می‌دهیم.")
        return None
    try:
        return joblib.load(MODEL_PATH)
    except Exception as e:
        logging.error(f"خطا در بارگذاری مدل: {e}")
        return None

def run_auto_optimization():
    """فراخوانی بهینه‌ساز با چک کردن مسیر دیتابیس"""
    try:
        # استفاده از مسیر مطلق برای دیتابیس
        db_path = getattr(database, 'DB_NAME', os.path.join(BASE_DIR, 'data', 'trading_bot.db'))
        if os.path.exists(db_path):
            with sqlite3.connect(db_path) as conn:
                count = conn.execute("SELECT count(*) FROM signals").fetchone()[0]
            
            if count > 0 and count % 50 == 0:
                logging.info(f"🚀 رسیدن به {count} معامله؛ شروع ارتقای هوشمند...")
                optimizer.optimize()
    except Exception as e:
        logging.error(f"خطا در پروسه خودارتقایی: {e}")

def run_bot():
    logging.info("🤖 اسکنر هوشمند v7.2 فعال شد.")
    database.init_db()
    
    # مدیریت پوزیشن‌های باز
    try:
        database.manage_open_positions()
    except Exception as e:
        logging.error(f"خطا در مدیریت پوزیشن‌ها: {e}")
    
    run_auto_optimization()
    
    # اسکن بازار
    watchlist = getattr(config, 'WATCHLIST', [])
    for pair in watchlist:
        try:
            df = coinex_client.get_coinex_candles(pair)
            if df is None or df.empty: continue
                
            df = indicators.calculate_indicators(df)
            signal_result = strategy.generate_signal(df, pair)
            
            if signal_result:
                database.save_signal_advanced(pair=pair, **signal_result)
                telegram_bot.format_and_send_signal(signal_result)
                logging.info(f"✅ سیگنال برای {pair} ارسال شد.")
        
        except Exception as e:
            logging.error(f"خطا در پردازش {pair}: {e}")
            time.sleep(1)

if __name__ == "__main__":
    run_bot()
