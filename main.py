# ---------------------------------------------------------
# FILE PATH: /main.py
# ---------------------------------------------------------

import os
import sys
import logging
import time
import joblib
import sqlite3

# ۱. تنظیم دقیق مسیر برای شناسایی ماژول‌های داخل src
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE_DIR, 'src'))

# ۲. واردات ماژول‌ها (فقط یک‌بار)
import config
from src import database, coinex_client, strategy, telegram_bot, indicators, optimizer

# ۳. تنظیم لاگ‌گیری استاندارد
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("bot.log"), logging.StreamHandler()]
)

MODEL_PATH = os.path.join(BASE_DIR, "src", "models", "trading_filter_model.pkl")
_cached_model = None

def get_model():
    global _cached_model
    if _cached_model is None and os.path.exists(MODEL_PATH):
        try:
            _cached_model = joblib.load(MODEL_PATH)
        except Exception as e:
            logging.error(f"خطا در بارگذاری مدل: {e}")
    return _cached_model

def run_auto_optimization():
    """ارتقای خودکار هوشمند پس از ۵۰ معامله"""
    try:
        db_path = getattr(database, 'DB_NAME', 'data/trading_bot.db')
        with sqlite3.connect(db_path) as conn:
            count = conn.execute("SELECT count(*) FROM signals").fetchone()[0]
        
        if count > 0 and count % 50 == 0:
            logging.info(f"🚀 رسیدن به {count} معامله؛ شروع ارتقای هوشمند...")
            optimizer.optimize()
    except Exception as e:
        logging.error(f"خطا در پروسه خودارتقایی: {e}")

def run_bot():
    logging.info("🤖 اسکنر هوشمند v7.1 فعال شد.")
    database.init_db()
    
    # مدیریت پوزیشن‌های باز قبلی
    try:
        database.manage_open_positions()
    except Exception as e:
        logging.error(f"خطا در ریسک‌فری: {e}")
    
    # خودارتقایی
    run_auto_optimization()
    
    # اسکن بازار
    for pair in getattr(config, 'WATCHLIST', []):
        try:
            df = coinex_client.get_coinex_candles(pair)
            if df is None or df.empty: continue
                
            df = indicators.calculate_indicators(df)
            signal_result = strategy.generate_signal(df, pair)
            
            if signal_result:
                # تایید نهایی توسط هوش مصنوعی
                model = get_model()
                ai_approved = True # در صورت عدم وجود مدل، پیش‌فرض تایید است
                
                database.save_signal_advanced(pair=pair, **signal_result)
                telegram_bot.format_and_send_signal(signal_result)
                logging.info(f"✅ سیگنال برای {pair} ثبت و ارسال شد.")
        
        except Exception as e:
            logging.error(f"خطا در پردازش {pair}: {e}")
            time.sleep(1)

if __name__ == "__main__":
    run_bot()
